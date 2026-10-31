import time
import webbrowser
from urllib.parse import quote

def enviar_mensaje_whatsapp(telefono, mensaje):
    mensaje_codificado = quote(mensaje)
    url = f"https://web.whatsapp.com/send?phone={telefono}&text={mensaje_codificado}"
    
    print(f"Abriendo WhatsApp para el número: {telefono}")
    webbrowser.open(url)
    
    # ⏳ Limitador de tiempo: Espera 12 segundos para que cargue el chat y puedas enviar
    print("Esperando 12 segundos para evitar spam...")
    time.sleep(12)

if __name__ == "__main__":
    # Abrimos nuestro archivo de texto simulando la base de datos
    with open("contactos.txt", "r", encoding="utf-8") as archivo:
        for linea in archivo:
            # Limpiamos espacios y separamos por la coma
            datos = linea.strip().split(",")
            if len(datos) == 2:
                nombre = datos[0]
                telefono = datos[1]
                
                # Creamos la variable personalizada con el nombre de cada contacto
                texto = f"¡Hola {nombre}! Este es un mensaje automatizado de prueba desde Python. 🚀"
                
                # Ejecutamos el envío
                enviar_mensaje_whatsapp(telefono, texto)
                
                print(f"Mensaje procesado para {nombre}.\n")