# Z.I.L Project

Z.I.L es una compañera de escritorio basada en IA que analiza tu pantalla, recuerda tus explicaciones y reacciona a través de un avatar de VTube Studio con voz y movimiento sincronizado.

## 1. Instalación de Dependencias

Para que el repositorio corra correctamente, debes instalar las siguientes librerías de Python.

### Librerías de Python
```bash
pip install python-dotenv websockets httpx chromadb Pillow sentence-transformers edge-tts mutagen numpy sounddevice openai-whisper torch mss psutil pywin32
```

### Requisitos Externos
*   **Ollama**: Necesitas tener instalado [Ollama](https://ollama.com/) y corriendo localmente. Asegúrate de haber descargado el modelo especificado en `core/config.py` (actualmente se esta utilizando el modelo `gemma4:e2b-it-q4_K_M`, si quieres cambiarlo, cambialo en la configuración tambien.).
*   **VTube Studio**: Debes tenerlo instalado en Steam, configura la ruta de ejecucion en `interface/avatarLoader.py`.

---

## 2. Configuración del Entorno (.env)

Crea un archivo llamado `.env` en la raíz del proyecto (donde está este README) con la siguiente estructura:


VTUBE_TOKEN=******
HF_TOKEN=******


---

## 3. Cómo obtener el Token de API de VTube Studio

Para obtener el token necesario para que Z.I.L controle tu avatar:

1.  Abre **VTube Studio**.
2.  Ve a **Configuración** -> **Plugins** (el icono de la pieza de rompecabezas).
3.  Asegúrate de que la opción **"API de VTube Studio"** esté activada.
4.  Ejecuta el script de conexión:
    ```bash
    python core/avatar/avatar.py
    ```
5.  Aparecerá un popup en VTube Studio preguntando si permites el acceso a "Z.I.L Project". Haz clic en **"Allow"** (Permitir).
6.  El script imprimirá el token en tu terminal. Cópialo y ponlo en el campo `VTUBE_TOKEN` de tu archivo `.env`.

---

## 4. Configuración de Parámetros en VTube Studio

Para que el avatar responda correctamente a los movimientos y el habla de Z.I.L, debes configurar los parámetros en VTube Studio:

1.  Abre **VTube Studio** y carga tu modelo.
2.  Ve a **Configuración** -> **Configuración del Modelo** (el icono de la persona con un engranaje).
3.  Busca los parámetros de ojos, boca y movimiento del cuerpo.
4.  Debes reemplazar el **Input** de los siguientes atributos por los parámetros creados por el API:

| Atributo | Parámetro a usar como **Input** |
| :--- | :--- |
| **Apertura de Boca** | `ZIL_MouthOpen` |
| **Forma de Boca (Sonrisa)** | `ZIL_MouthSmile` |
| **Rotación Cabeza X** | `ZIL_FaceAngleX` |
| **Rotación Cabeza Y** | `ZIL_FaceAngleY` |
| **Movimiento Ojo X** | `ZIL_EyeX` |
| **Movimiento Ojo Y** | `ZIL_EyeY` |

*Nota: Estos parámetros se crean automáticamente la primera vez que el script se conecta exitosamente a VTube Studio.*

---

## 5. Ejecución del Proyecto

Para iniciar el sistema completo:

1.  **Abre Steam**.
2.  Ejecuta el archivo principal:
```bash
python zil_main.py
```

¡Z.I.L se activará, abrirá tu avatar y empezará a observar tu pantalla y escucharte!

## 6. Memoria de Z.I.L

Si ejecutas el visor de memoria, podrás observar los conocimientos y recuerdos que Z.I.L ha generado y guardado en su base de datos:

```bash
python utilities/memory_viewer.py
```

*Nota: Si el sistema no se ha ejecutado antes o Z.I.L no ha aprendido nada aún a través de conversaciones, no verás ninguna memoria listada.*
