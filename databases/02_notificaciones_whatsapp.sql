-- =====================================================================
-- 02_notificaciones_whatsapp.sql
-- Extiende lexiscan_db con preferencias de notificación, una cola de
-- mensajes y control de intervalo entre mensajes de WhatsApp.
--
-- Ejecutar DESPUÉS de lexiscan_db.sql. Requiere MySQL 8.0.16 o superior.
-- Las secciones 1 y 2 (ALTER TABLE) solo se pueden ejecutar UNA vez;
-- el resto del script se puede volver a correr sin problema.
-- =====================================================================
USE lexiscan_db;

-- 1. Fecha y hora del último WhatsApp enviado a cada usuario
ALTER TABLE notificaciones
    ADD COLUMN ultimo_whatsapp DATETIME NULL AFTER whatsapp;

-- 2. El usuario debe elegir al menos un medio (correo, WhatsApp o ambos)
ALTER TABLE notificaciones
    ADD CONSTRAINT chk_notificacion_medio CHECK (correo OR whatsapp);

-- 3. Intervalos configurables (valores de partida, ajustar según el proveedor)
--    GLOBAL: segundos mínimos entre dos WhatsApp cualesquiera (número emisor)
--    USUARIO: segundos mínimos entre dos WhatsApp al mismo usuario
INSERT IGNORE INTO parametros (nombre, valor, descripcion) VALUES
('WHATSAPP_INTERVALO_GLOBAL_SEG', '30', 'Segundos mínimos entre dos mensajes de WhatsApp cualesquiera'),
('WHATSAPP_INTERVALO_USUARIO_SEG', '300', 'Segundos mínimos entre dos mensajes de WhatsApp al mismo usuario');

-- 4. Cola de mensajes (correo y WhatsApp)
CREATE TABLE IF NOT EXISTS cola_mensajes (
    id_mensaje INT AUTO_INCREMENT PRIMARY KEY,
    id_usuario INT NOT NULL,
    canal VARCHAR(10) NOT NULL,                       -- CORREO o WHATSAPP
    tipo VARCHAR(30) NOT NULL,                        -- CREDENCIAL, RECUPERACION, REPORTE
    destino VARCHAR(150) NOT NULL,                    -- correo o teléfono al programar
    contenido VARCHAR(1000),
    ruta_adjunto VARCHAR(500),
    estado VARCHAR(15) NOT NULL DEFAULT 'PENDIENTE',  -- PENDIENTE, ENVIANDO, ENVIADO, ERROR
    programado_para DATETIME NOT NULL,                -- no enviar antes de esta hora
    fecha_envio DATETIME NULL,                        -- fecha y hora reales del envío
    intentos INT NOT NULL DEFAULT 0,
    error VARCHAR(250),
    fecha_creacion DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_mensaje_usuario
        FOREIGN KEY (id_usuario)
        REFERENCES usuarios(id_usuario)
        ON UPDATE CASCADE
        ON DELETE CASCADE,

    CONSTRAINT chk_mensaje_canal
        CHECK (canal IN ('CORREO', 'WHATSAPP')),

    CONSTRAINT chk_mensaje_estado
        CHECK (estado IN ('PENDIENTE', 'ENVIANDO', 'ENVIADO', 'ERROR')),

    INDEX idx_mensaje_pendientes (estado, programado_para),
    INDEX idx_mensaje_usuario_canal (id_usuario, canal)
);

-- 5. Programar un mensaje
--    Valida que el usuario tenga habilitado el medio y, para WhatsApp,
--    calcula la hora más temprana permitida según el último mensaje del usuario.
--    Devuelve id_mensaje y programado_para.
DROP PROCEDURE IF EXISTS sp_programar_mensaje;
DELIMITER //
CREATE PROCEDURE sp_programar_mensaje(
    IN p_id_usuario INT,
    IN p_canal VARCHAR(10),
    IN p_tipo VARCHAR(30),
    IN p_contenido VARCHAR(1000),
    IN p_ruta_adjunto VARCHAR(500)
)
BEGIN
    DECLARE v_destino VARCHAR(150) DEFAULT NULL;
    DECLARE v_habilitado BOOLEAN DEFAULT FALSE;
    DECLARE v_gap_usuario INT DEFAULT 300;
    DECLARE v_ultimo DATETIME DEFAULT NULL;
    DECLARE v_slot DATETIME;
    DECLARE v_id INT;

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        DO RELEASE_LOCK('cola_mensajes');
        RESIGNAL;
    END;

    IF p_canal NOT IN ('CORREO', 'WHATSAPP') THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Canal no válido';
    END IF;

    SELECT IF(p_canal = 'WHATSAPP', u.telefono, u.correo),
           IF(p_canal = 'WHATSAPP', n.whatsapp, n.correo)
    INTO v_destino, v_habilitado
    FROM usuarios u
    JOIN notificaciones n ON n.id_usuario = u.id_usuario
    WHERE u.id_usuario = p_id_usuario;

    IF NOT v_habilitado OR v_destino IS NULL THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'El usuario no tiene habilitado este medio de notificación';
    END IF;

    -- Bloqueo para que dos peticiones simultáneas no reciban la misma hora
    IF IFNULL(GET_LOCK('cola_mensajes', 5), 0) <> 1 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'No se pudo bloquear la cola de mensajes';
    END IF;

    SET v_slot = NOW();

    IF p_canal = 'WHATSAPP' THEN
        SELECT IFNULL(MAX(CAST(valor AS UNSIGNED)), 300) INTO v_gap_usuario
        FROM parametros
        WHERE nombre = 'WHATSAPP_INTERVALO_USUARIO_SEG' AND estado = TRUE;

        -- Último mensaje de este usuario: el envío real, o la hora programada si aún no sale
        SELECT MAX(COALESCE(fecha_envio, programado_para)) INTO v_ultimo
        FROM cola_mensajes
        WHERE id_usuario = p_id_usuario
          AND canal = 'WHATSAPP'
          AND estado IN ('PENDIENTE', 'ENVIANDO', 'ENVIADO');

        IF v_ultimo IS NOT NULL THEN
            SET v_slot = GREATEST(v_slot, DATE_ADD(v_ultimo, INTERVAL v_gap_usuario SECOND));
        END IF;
    END IF;

    INSERT INTO cola_mensajes
        (id_usuario, canal, tipo, destino, contenido, ruta_adjunto, programado_para)
    VALUES
        (p_id_usuario, p_canal, p_tipo, v_destino, p_contenido, p_ruta_adjunto, v_slot);

    SET v_id = LAST_INSERT_ID();
    DO RELEASE_LOCK('cola_mensajes');

    SELECT v_id AS id_mensaje, v_slot AS programado_para;
END //
DELIMITER ;

-- 6. Tomar el siguiente mensaje listo para enviar (lo llama el worker del backend)
--    Para WhatsApp respeta el intervalo global entre mensajes.
--    Siempre devuelve un resultado; si no hay nada que enviar, viene vacío.
--    Pensado para UN solo worker de envío.
DROP PROCEDURE IF EXISTS sp_tomar_siguiente_mensaje;
DELIMITER //
CREATE PROCEDURE sp_tomar_siguiente_mensaje(IN p_canal VARCHAR(10))
BEGIN
    DECLARE v_gap_global INT DEFAULT 30;
    DECLARE v_ultimo DATETIME DEFAULT NULL;
    DECLARE v_id INT DEFAULT NULL;
    DECLARE v_puede BOOLEAN DEFAULT TRUE;

    IF p_canal = 'WHATSAPP' THEN
        SELECT IFNULL(MAX(CAST(valor AS UNSIGNED)), 30) INTO v_gap_global
        FROM parametros
        WHERE nombre = 'WHATSAPP_INTERVALO_GLOBAL_SEG' AND estado = TRUE;

        SELECT MAX(fecha_envio) INTO v_ultimo
        FROM cola_mensajes
        WHERE canal = 'WHATSAPP' AND estado IN ('ENVIANDO', 'ENVIADO');

        IF v_ultimo IS NOT NULL
           AND v_ultimo > DATE_SUB(NOW(), INTERVAL v_gap_global SECOND) THEN
            SET v_puede = FALSE;
        END IF;
    END IF;

    IF v_puede THEN
        START TRANSACTION;

        SELECT id_mensaje INTO v_id
        FROM cola_mensajes
        WHERE canal = p_canal
          AND estado = 'PENDIENTE'
          AND programado_para <= NOW()
        ORDER BY programado_para, id_mensaje
        LIMIT 1
        FOR UPDATE SKIP LOCKED;

        IF v_id IS NOT NULL THEN
            UPDATE cola_mensajes
            SET estado = 'ENVIANDO', fecha_envio = NOW(), intentos = intentos + 1
            WHERE id_mensaje = v_id;
        END IF;

        COMMIT;
    END IF;

    SELECT * FROM cola_mensajes WHERE id_mensaje = v_id;
END //
DELIMITER ;

-- 7. Marcar el resultado del envío
--    Si fue exitoso y era WhatsApp, guarda la fecha/hora en notificaciones.ultimo_whatsapp
DROP PROCEDURE IF EXISTS sp_marcar_mensaje;
DELIMITER //
CREATE PROCEDURE sp_marcar_mensaje(
    IN p_id_mensaje INT,
    IN p_exito BOOLEAN,
    IN p_error VARCHAR(250)
)
BEGIN
    UPDATE cola_mensajes
    SET estado = IF(p_exito, 'ENVIADO', 'ERROR'),
        error = IF(p_exito, NULL, p_error)
    WHERE id_mensaje = p_id_mensaje AND estado = 'ENVIANDO';

    IF p_exito THEN
        UPDATE notificaciones n
        JOIN cola_mensajes c ON c.id_usuario = n.id_usuario
        SET n.ultimo_whatsapp = c.fecha_envio
        WHERE c.id_mensaje = p_id_mensaje AND c.canal = 'WHATSAPP';
    END IF;
END //
DELIMITER ;

-- =====================================================================
-- PRUEBA RÁPIDA (descomentar). Usuario ficticio; asume que su id_usuario es 1.
-- El hash no sirve para iniciar sesión, solo para probar la cola.
-- =====================================================================
-- INSERT INTO usuarios (correo, telefono, fecha_nacimiento, nickname, password_hash)
-- VALUES ('prueba@ejemplo.com', '+50255550000', '2000-01-01', 'prueba', 'HASH_DE_PRUEBA');
-- INSERT INTO notificaciones (id_usuario, correo, whatsapp) VALUES (LAST_INSERT_ID(), FALSE, TRUE);
--
-- CALL sp_programar_mensaje(1, 'WHATSAPP', 'CREDENCIAL', 'Hola, esta es tu credencial', NULL);
-- CALL sp_programar_mensaje(1, 'WHATSAPP', 'REPORTE', 'Tu reporte está listo', NULL);
-- SELECT id_mensaje, estado, programado_para FROM cola_mensajes;  -- el 2.º queda 5 min después
--
-- CALL sp_tomar_siguiente_mensaje('WHATSAPP');   -- devuelve el 1.º y lo marca ENVIANDO
-- CALL sp_marcar_mensaje(1, TRUE, NULL);         -- lo marca ENVIADO y guarda ultimo_whatsapp
