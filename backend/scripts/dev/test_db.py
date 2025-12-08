import os
import psycopg2
from dotenv import load_dotenv

# Cargar las variables de entorno desde el archivo .env
load_dotenv()

print("Intentando conectar a la base de datos PostgreSQL...")

try:
    # Lee las credenciales desde las variables de entorno
    # Asegúrate de que los nombres de las variables coincidan con los de tu .env
    conn = psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432") # Usa 5432 como puerto por defecto
    )

    # Si la conexión es exitosa, imprime un mensaje
    print("✅ ¡Conexión exitosa a la base de datos!")

    # Cierra la conexión
    conn.close()

except psycopg2.OperationalError as e:
    print("❌ Error en la conexión:")
    print(f"   Detalle: {e}")
    print("\n   Posibles causas:")
    print("   1. ¿Las credenciales (usuario, contraseña, nombre de la DB) en .env son correctas?")
    print("   2. ¿El servidor de PostgreSQL está corriendo en el host y puerto especificados?")
    print("   3. ¿El firewall permite la conexión a ese puerto?")

except Exception as e:
    print(f"❌ Ocurrió un error inesperado: {e}")
