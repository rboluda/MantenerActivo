# Mantener Activo

Utilidad para Windows 10/11 que evita que el equipo se suspenda o bloquee por
inactividad moviendo el ratón de vez en cuando con un movimiento de aspecto
humano.

## Funciones

- Intervalo aleatorio entre un mínimo y un máximo configurables.
- Amplitud del movimiento ajustable; opción de volver al punto de origen.
- Solo mueve el ratón si el usuario lleva un tiempo inactivo (opcional).
- Refuerzo con `SetThreadExecutionState` para impedir la suspensión del
  sistema y, opcionalmente, el apagado de la pantalla.
- Cuenta atrás hasta la próxima interacción y globos de ayuda en cada opción.
- Se minimiza a la bandeja del sistema; se sale desde el menú del icono.

## Ejecutar desde el código

Requiere Python 3 en Windows.

```bash
pip install -r requirements.txt
python MantenerActivo.py
```

Sin `pystray`/`pillow` la aplicación funciona igualmente, pero sin icono en la
bandeja (la X cierra el programa).

## Compilar el ejecutable

```bash
pip install pyinstaller
pyinstaller MantenerActivo.spec
```

El resultado queda en `dist/MantenerActivo.exe` (un único archivo, sin
consola, con el icono `raton.ico` incluido).
