-- =====================================================================
-- 03_reprogramar_mensaje.sql
-- Agrega la reprogramación de mensajes fallidos. Ejecutar DESPUÉS de
-- 02_notificaciones_whatsapp.sql. Se puede volver a correr sin problema.
-- =====================================================================
USE lexiscan_db;

INSERT IGNORE INTO parametros (nombre, valor, descripcion) VALUES
('MENSAJES_MAX_INTENTOS', '3', 'Intentos máximos de envío antes de dejar un mensaje en ERROR definitivo');

-- Devuelve un mensaje en ERROR a la cola (PENDIENTE) con una nueva hora.
-- La nueva hora es la mayor entre: ahora + retraso, y el último mensaje de
-- WhatsApp del usuario + intervalo (sin contar este mismo mensaje).
-- Limpia fecha_envio para que el intento fallido no cuente como "último envío".
DROP PROCEDURE IF EXISTS sp_reprogramar_mensaje;
DELIMITER //
CREATE PROCEDURE sp_reprogramar_mensaje(
    IN p_id_mensaje INT,
    IN p_retraso_seg INT
)
BEGIN
    DECLARE v_id_usuario INT DEFAULT NULL;
    DECLARE v_canal VARCHAR(10) DEFAULT NULL;
    DECLARE v_estado VARCHAR(15) DEFAULT NULL;
    DECLARE v_intentos INT DEFAULT 0;
    DECLARE v_max INT DEFAULT 3;
    DECLARE v_gap_usuario INT DEFAULT 300;
    DECLARE v_ultimo DATETIME DEFAULT NULL;
    DECLARE v_slot DATETIME;

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        DO RELEASE_LOCK('cola_mensajes');
        RESIGNAL;
    END;

    SELECT id_usuario, canal, estado, intentos
    INTO v_id_usuario, v_canal, v_estado, v_intentos
    FROM cola_mensajes
    WHERE id_mensaje = p_id_mensaje;

    IF v_estado IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El mensaje no existe';
    END IF;

    IF v_estado <> 'ERROR' THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Solo se pueden reprogramar mensajes en estado ERROR';
    END IF;

    SELECT IFNULL(MAX(CAST(valor AS UNSIGNED)), 3) INTO v_max
    FROM parametros
    WHERE nombre = 'MENSAJES_MAX_INTENTOS' AND estado = TRUE;

    IF v_intentos >= v_max THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'El mensaje alcanzó el máximo de intentos';
    END IF;

    IF IFNULL(GET_LOCK('cola_mensajes', 5), 0) <> 1 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'No se pudo bloquear la cola de mensajes';
    END IF;

    SET v_slot = DATE_ADD(NOW(), INTERVAL GREATEST(IFNULL(p_retraso_seg, 0), 0) SECOND);

    IF v_canal = 'WHATSAPP' THEN
        SELECT IFNULL(MAX(CAST(valor AS UNSIGNED)), 300) INTO v_gap_usuario
        FROM parametros
        WHERE nombre = 'WHATSAPP_INTERVALO_USUARIO_SEG' AND estado = TRUE;

        SELECT MAX(COALESCE(fecha_envio, programado_para)) INTO v_ultimo
        FROM cola_mensajes
        WHERE id_usuario = v_id_usuario
          AND canal = 'WHATSAPP'
          AND estado IN ('PENDIENTE', 'ENVIANDO', 'ENVIADO')
          AND id_mensaje <> p_id_mensaje;

        IF v_ultimo IS NOT NULL THEN
            SET v_slot = GREATEST(v_slot, DATE_ADD(v_ultimo, INTERVAL v_gap_usuario SECOND));
        END IF;
    END IF;

    UPDATE cola_mensajes
    SET estado = 'PENDIENTE', programado_para = v_slot, fecha_envio = NULL
    WHERE id_mensaje = p_id_mensaje;

    DO RELEASE_LOCK('cola_mensajes');

    SELECT p_id_mensaje AS id_mensaje, v_slot AS programado_para, 'PENDIENTE' AS estado;
END //
DELIMITER ;