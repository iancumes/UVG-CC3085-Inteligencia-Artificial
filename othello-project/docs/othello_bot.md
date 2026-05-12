# Bot competitivo de Othello CC3085

## Como ejecutarlo

Desde la raiz del proyecto:

```bash
cd othello-project
python -m client.competitive_bot \
  --server-url http://localhost:8000 \
  --tournament-name "Nombre del torneo" \
  --username "mi-bot"
```

Para el servidor de prueba que compartio el catedratico:

```bash
cd othello-project
python -m client.competitive_bot \
  --server-url https://d9df-190-14-11-2.ngrok-free.app \
  --tournament-name test_mayo11 \
  --username "tu-usuario"
```

Para el dia del torneo se usa el mismo formato que el ejemplo de clase. La unica diferencia es reemplazar `client.sample_bot` por `client.competitive_bot`:

```bash
python -m client.competitive_bot \
  --server-url "URL_DEL_CATEDRATICO" \
  --tournament-name "NOMBRE_DEL_TORNEO" \
  --username "tu-usuario"
```

Ejemplo con el formato que dio en clase:

```bash
python -m client.competitive_bot \
  --server-url https://c792-190-56-194-12.ngrok-free.app \
  --tournament-name FIRST_TEST \
  --username "tu-usuario"
```

El servidor remoto lo levanta el catedratico. Para competir no se corre `uvicorn`, no se modifica el servidor y no se usa Docker; solo se deja corriendo este proceso del bot en la terminal.

Parametros utiles:

- `--move-budget-seconds`: presupuesto por turno. El valor por defecto es `2.65`, dejando margen antes del limite de 3 segundos.
- `--max-depth`: profundidad maxima de busqueda. El valor por defecto es `8`.
- `--log-level`: nivel de logs, por ejemplo `INFO` o `DEBUG`.

Archivos agregados:

- `client/othello_ai.py`: reglas locales de Othello, evaluacion heuristica, minimax/negamax, poda alfa-beta y manejo de tiempo.
- `client/competitive_bot.py`: cliente ejecutable que conecta el bot al servidor del torneo.
- `tests/test_othello_ai.py`: pruebas unitarias y una partida simulada contra movimientos aleatorios.

## Como verificarlo por UI

### Opcion local

Esta opcion sirve para probar el bot antes del torneo usando el dashboard incluido en el repo.

Terminal 1, backend:

```bash
cd othello-project
export MOVE_TIMEOUT_SECONDS=3
export ADMIN_USERNAME=admin
export ADMIN_PASSWORD=admin123
.venv/bin/uvicorn server.main:app --reload
```

Terminal 2, dashboard:

```bash
cd othello-project/admin
cp .env.local.example .env.local
npm install
npm run dev
```

Abrir `http://localhost:3000`, iniciar sesion con `admin` / `admin123`, crear un torneo, abrir registro, y luego correr bots en otras terminales:

```bash
cd othello-project
python -m client.competitive_bot \
  --server-url http://localhost:8000 \
  --tournament-name "Nombre del torneo local" \
  --username "bot-competitivo"
```

Para tener oponente rapido:

```bash
python -m client.sample_bot \
  --server-url http://localhost:8000 \
  --tournament-name "Nombre del torneo local" \
  --username "bot-random"
```

En el dashboard se puede revisar:

- `Players`: el bot aparece conectado.
- `Live Games`: tablero en vivo, turno actual y conteo.
- `Games`: historial de jugadas.
- `Standings`: resultado despues de cerrar la ronda.

### Opcion con servidor remoto del catedratico

Si el catedratico solo da URL y nombre del torneo, se verifica principalmente en la terminal: debe aparecer un log de inscripcion, conexion y movimientos seleccionados. Ejemplo:

```text
Enrolled in tournament test_mayo11 as tu-usuario
Connecting to wss://...
Selected move=d3 color=B depth=...
Submitted move d3 for game ...
```

Para verlo por UI contra el servidor remoto hay dos posibilidades:

- Si el catedratico comparte dashboard/admin, entrar ahi y revisar `Players`, `Live Games` y `Standings`.
- Si da credenciales admin para el backend remoto, se puede correr el dashboard local apuntando a su URL:

```bash
cd othello-project/admin
cat > .env.local <<'EOF'
NEXT_PUBLIC_API_BASE_URL=https://d9df-190-14-11-2.ngrok-free.app
NEXT_PUBLIC_WS_BASE_URL=wss://d9df-190-14-11-2.ngrok-free.app
EOF
npm run dev
```

Luego abrir `http://localhost:3000` e iniciar sesion con las credenciales que el catedratico proporcione. Sin credenciales admin, la UI local no puede consultar el panel administrativo remoto.

## Idea general

Othello se puede modelar como un problema de busqueda adversarial: el estado es el tablero, las acciones son los movimientos legales, el modelo de transicion voltea fichas, y el objetivo es terminar con mas fichas que el oponente. Como ambos jugadores toman decisiones opuestas, el bot usa minimax en forma negamax.

La busqueda completa del arbol no es viable dentro de 3 segundos. Por eso el bot usa tres tecnicas:

- Poda alfa-beta: evita explorar ramas que ya no pueden mejorar la decision final.
- Profundizacion iterativa: busca a profundidad 1, luego 2, luego 3, etc. Si el tiempo se acaba, siempre conserva la mejor jugada de la ultima profundidad completada.
- Heuristicas: estima la calidad de tableros no terminales para decidir sin llegar al final de la partida.

## Heuristica

La funcion de evaluacion combina varios criterios:

- Esquinas: son muy valiosas porque no se pueden voltear.
- Movilidad: favorece tener mas movimientos disponibles que el oponente.
- Matriz posicional: premia casillas estrategicas y penaliza casillas peligrosas cerca de esquinas vacias.
- Frontera: penaliza fichas expuestas junto a espacios vacios.
- Estabilidad aproximada: premia fichas conectadas a esquinas propias por los bordes.
- Diferencia de fichas: tiene poco peso al inicio y mucho peso al final.

El peso cambia segun la fase de la partida. Al inicio se prioriza movilidad y posicion; al final se prioriza el conteo de fichas.

## Pseudocodigo

### Seleccion de movimiento

```text
funcion elegir_movimiento(tablero, color, movimientos_legales):
    si movimientos_legales esta vacio:
        retornar "pass"

    mejor_movimiento = mejor_movimiento_rapido(movimientos_legales)
    limite = tiempo_actual + 2.65 segundos

    para profundidad desde 1 hasta max_depth:
        si tiempo_actual >= limite:
            romper

        intento = buscar_con_alfa_beta(tablero, color, profundidad, limite)
        si intento termino antes del limite:
            mejor_movimiento = intento.movimiento
        si no:
            romper

    retornar mejor_movimiento
```

### Negamax con alfa-beta

```text
funcion negamax(tablero, color, profundidad, alfa, beta):
    si se acabo el tiempo:
        detener busqueda

    movimientos = movimientos_legales(tablero, color)

    si no hay movimientos para ningun jugador:
        retornar valor_terminal(tablero, color)

    si profundidad == 0:
        retornar heuristica(tablero, color)

    si movimientos esta vacio:
        retornar -negamax(tablero, oponente(color), profundidad - 1, -beta, -alfa)

    mejor = -infinito
    para movimiento en ordenar_movimientos(movimientos):
        nuevo_tablero = aplicar_movimiento(tablero, movimiento, color)
        siguiente = color_del_siguiente_turno(nuevo_tablero, color)

        si siguiente == color:
            valor = negamax(nuevo_tablero, color, profundidad - 1, alfa, beta)
        si no:
            valor = -negamax(nuevo_tablero, siguiente, profundidad - 1, -beta, -alfa)

        mejor = max(mejor, valor)
        alfa = max(alfa, valor)

        si alfa >= beta:
            romper

    retornar mejor
```

## Relacion con temas de clase

- Formulacion de problemas: se definieron estado, acciones, transicion, objetivo y costo/utilidad.
- Busqueda: el bot explora secuencias posibles de movimientos antes de actuar.
- Busqueda informada: la heuristica agrega informacion externa para evaluar estados no terminales.
- Optimizacion: alfa-beta reduce el numero de nodos explorados y mejora el uso del limite de tiempo.
- Evaluacion de desempeno: las pruebas verifican legalidad, tiempo de respuesta y partidas completas contra un jugador aleatorio.

## Nota sobre el PDF

El archivo `CC3085 Proyecto Final.pdf` indica torneo presencial el lunes 25 de mayo de 2026 a las 5:20 PM. En la seccion del reporte escrito aparece "viernes 5 de junio, 2025"; esa fecha parece inconsistente con el resto del documento y debe confirmarse con el catedratico.
