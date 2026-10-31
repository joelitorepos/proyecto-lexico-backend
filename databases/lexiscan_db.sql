CREATE DATABASE IF NOT EXISTS lexiscan_db;
USE lexiscan_db;

-- 1. Tabla de Roles
CREATE TABLE IF NOT EXISTS roles (
    id_rol INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(30) NOT NULL UNIQUE,
    descripcion VARCHAR(255),
    estado BOOLEAN NOT NULL DEFAULT TRUE
);

-- Insertar roles por defecto
INSERT IGNORE INTO roles (id_rol, nombre, descripcion) VALUES 
(1, 'Admin', 'Administrador del sistema'),
(2, 'Usuario', 'Usuario estándar');

-- 2. Tabla de Usuarios Centralizada
CREATE TABLE IF NOT EXISTS usuarios (
    id_usuario INT AUTO_INCREMENT PRIMARY KEY,
    id_rol INT NOT NULL DEFAULT 2,
    correo VARCHAR(150) NOT NULL UNIQUE,
    telefono VARCHAR(20) NOT NULL,
    fecha_nacimiento DATE NOT NULL,
    nickname VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL, -- Diseñado para BCrypt (Soporta hashes >= 60 caracteres)
    estado BOOLEAN NOT NULL DEFAULT TRUE,
    fecha_registro DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ultimo_login DATETIME NULL,

    CONSTRAINT fk_usuario_rol
        FOREIGN KEY (id_rol)
        REFERENCES roles(id_rol)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    INDEX idx_usuario_correo (correo),
    INDEX idx_usuario_nickname (nickname)
);

-- 3. Tabla de Fotografías (1 : N)
CREATE TABLE IF NOT EXISTS fotografias (
    id_fotografia INT AUTO_INCREMENT PRIMARY KEY,
    id_usuario INT NOT NULL,
    ruta_original VARCHAR(500) NOT NULL,
    ruta_modificada VARCHAR(500),
    rostro_recortado VARCHAR(500),
    filtro VARCHAR(100),
    fecha_actualizacion DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,

    CONSTRAINT fk_fotografia_usuario
        FOREIGN KEY (id_usuario)
        REFERENCES usuarios(id_usuario)
        ON UPDATE CASCADE
        ON DELETE CASCADE,

    INDEX idx_fotografia_usuario (id_usuario)
);

-- 4. Tabla de Notificaciones (1 : 1)
CREATE TABLE IF NOT EXISTS notificaciones (
    id_notificacion INT AUTO_INCREMENT PRIMARY KEY,
    id_usuario INT NOT NULL UNIQUE,
    correo BOOLEAN NOT NULL DEFAULT FALSE,
    whatsapp BOOLEAN NOT NULL DEFAULT FALSE,
    fecha_actualizacion DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,

    CONSTRAINT fk_notificacion_usuario
        FOREIGN KEY (id_usuario)
        REFERENCES usuarios(id_usuario)
        ON UPDATE CASCADE
        ON DELETE CASCADE
);

-- 5. Tabla de Credenciales (1 : N)
CREATE TABLE IF NOT EXISTS credenciales (
    id_credencial INT AUTO_INCREMENT PRIMARY KEY,
    id_usuario INT NOT NULL,
    codigo_qr VARCHAR(500) NOT NULL,
    ruta_pdf VARCHAR(500) NOT NULL,
    fecha_generacion DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    estado BOOLEAN NOT NULL DEFAULT TRUE,

    CONSTRAINT fk_credencial_usuario
        FOREIGN KEY (id_usuario)
        REFERENCES usuarios(id_usuario)
        ON UPDATE CASCADE
        ON DELETE CASCADE,

    INDEX idx_credencial_usuario (id_usuario)
);

-- 6. Tabla de Tokens de Recuperación (1 : N)
CREATE TABLE IF NOT EXISTS tokens_recuperacion (
    id_token INT AUTO_INCREMENT PRIMARY KEY,
    id_usuario INT NOT NULL,
    token VARCHAR(255) NOT NULL UNIQUE,
    fecha_creacion DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_expiracion DATETIME NOT NULL,
    utilizado BOOLEAN NOT NULL DEFAULT FALSE,

    CONSTRAINT fk_token_usuario
        FOREIGN KEY (id_usuario)
        REFERENCES usuarios(id_usuario)
        ON UPDATE CASCADE
        ON DELETE CASCADE,

    INDEX idx_token_usuario (id_usuario),
    INDEX idx_token (token)
);

-- 7. Tabla de Bitácora / Auditoría (1 : N)
CREATE TABLE IF NOT EXISTS bitacora (
    id_bitacora INT AUTO_INCREMENT PRIMARY KEY,
    id_usuario INT NOT NULL,
    accion VARCHAR(100) NOT NULL,
    descripcion VARCHAR(250),
    fecha_hora DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ip VARCHAR(45) NOT NULL, -- Compatible con IPv4 e IPv6

    CONSTRAINT fk_bitacora_usuario
        FOREIGN KEY (id_usuario)
        REFERENCES usuarios(id_usuario)
        ON UPDATE CASCADE
        ON DELETE CASCADE,

    INDEX idx_bitacora_usuario (id_usuario),
    INDEX idx_bitacora_fecha (fecha_hora)
);

-- 8. Tabla de Análisis (1 : N)
CREATE TABLE IF NOT EXISTS analisis (
    id_analisis INT AUTO_INCREMENT PRIMARY KEY,
    id_usuario INT NOT NULL,
    nombre_archivo VARCHAR(255) NOT NULL,
    idioma VARCHAR(30) NOT NULL,
    ruta_archivo VARCHAR(500) NOT NULL,
    cantidad_palabras INT NOT NULL DEFAULT 0,
    fecha_analisis DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    estado VARCHAR(30) NOT NULL DEFAULT 'PENDIENTE',

    CONSTRAINT fk_analisis_usuario
        FOREIGN KEY (id_usuario)
        REFERENCES usuarios(id_usuario)
        ON UPDATE CASCADE
        ON DELETE CASCADE,

    CONSTRAINT chk_analisis_cantidad
        CHECK (cantidad_palabras >= 0),

    INDEX idx_analisis_usuario (id_usuario)
);

-- 9. Tabla de Resultados de Análisis (1 : N)
CREATE TABLE IF NOT EXISTS resultados_analisis (
    id_resultado INT AUTO_INCREMENT PRIMARY KEY,
    id_analisis INT NOT NULL,
    categoria VARCHAR(50) NOT NULL,
    token VARCHAR(255) NOT NULL,
    frecuencia INT NOT NULL DEFAULT 0,
    raiz VARCHAR(255),

    CONSTRAINT fk_resultado_analisis
        FOREIGN KEY (id_analisis)
        REFERENCES analisis(id_analisis)
        ON UPDATE CASCADE
        ON DELETE CASCADE,

    CONSTRAINT chk_resultado_frecuencia
        CHECK (frecuencia >= 0),

    INDEX idx_resultado_analisis (id_analisis)
);

-- 10. Tabla de Parámetros
CREATE TABLE IF NOT EXISTS parametros (
    id_parametro INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL UNIQUE,
    valor VARCHAR(255) NOT NULL,
    descripcion VARCHAR(500),
    estado BOOLEAN NOT NULL DEFAULT TRUE
);

-- PROCEDIMIENTO ALMACENADO PARA AUDITORÍA DE LOGIN
DELIMITER //
CREATE PROCEDURE sp_registrar_login(
    IN p_id_usuario INT,
    IN p_ip VARCHAR(45),
    IN p_descripcion VARCHAR(250)
)
BEGIN
    -- 1. Inserta el log de inicio de sesión en la bitácora
    INSERT INTO bitacora (id_usuario, accion, descripcion, fecha_hora, ip)
    VALUES (p_id_usuario, 'LOGIN', IFNULL(p_descripcion, 'Inicio de sesión exitoso'), NOW(), p_ip);

    -- 2. Actualiza la marca de tiempo de último login en el usuario
    UPDATE usuarios 
    SET ultimo_login = NOW()
    WHERE id_usuario = p_id_usuario;
END //

DELIMITER ;
