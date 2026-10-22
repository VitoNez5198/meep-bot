# Spec: LoL Assistant

## Propósito
Proveer asistencia estadística y de equipamiento (runas, habilidades e ítems) para jugadores de League of Legends directamente a través de mensajes enriquecidos e interactivos en Discord, optimizado para consulta rápida durante la selección de campeones.

## Requisitos y Comportamiento

### 1. Consulta Unificada de Campeón: `/champion <campeón> [modo_o_rol]`
* **Comandos**: `/champion <campeón> [modo_o_rol]` (Alias de texto: `!c <campeón> [modo_o_rol]` y alias secundario `/build`).
* **Entrada**:
  * Nombre del campeón (soporta nombres completos y alias comunes como `mf`, `tf`, `cait`, `nunu`, `asol`).
  * Parámetro opcional `modo_o_rol`:
    * Si se omite: muestra por defecto la build para **Grieta del Invocador** (Normal/Ranked).
    * Si se pasa `aram`: muestra directamente la build optimizada para **ARAM**.
    * Si se pasa un rol (`top`, `jungle`, `mid`, `adc`, `support`): filtra por ese carril en la Grieta.
* **Salida Visual (Discord Embed)**:
  * Icono y miniatura del campeón extraídos de Riot DataDragon.
  * Runas recomendadas: Árbol principal con runa clave, árbol secundario y 3 fragmentos de estadísticas.
  * Secuencia de maxeo de habilidades (ej: Q > E > W).
  * Hechizos de invocador recomendados (ej: Flash + Curación / Extenuación).
  * Objetos recomendados: Objeto inicial, 3 Core Items y 3 Objetos situacionales con nombres claros.
* **Selector de Variantes con Botones Interactivos (`discord.ui.Button`)**:
  * Cuando el campeón posee estilos alternativos viables (ej. en ARAM: Miss Fortune AD vs AP, Malphite Tanque vs AP, Kai'Sa AP vs AD; o en Grieta según rol/build):
    * El bot muestra por defecto la opción con mayor win rate.
    * Añade botones interactivos abajo (ej: `[ 🏹 AD / Letalidad ]` y `[ 🔮 AP / Poke ]`).
    * Al hacer clic en un botón, el mensaje se actualiza al instante con las runas, habilidades e ítems correspondientes.
    * También permite pasar la variante directamente por texto (ej: `!c mf aram ap`).

### 3. Counters y Enfrentamientos
* **Comando**: `/counters <campeón>` o `!counters <campeón>`
* **Salida**: Embed con los 3 enfrentamientos más difíciles (peor win rate) y los 3 más favorables para ese campeón en su carril principal.

### 4. Partida en Vivo
* **Comando**: `/live [invocador]` o `!live [invocador]`
* **Salida**: Si el invocador se encuentra en partida activa (vía Riot Spectator API), muestra:
  * Campeón jugado por cada integrante de ambos equipos.
  * Rango clasificado actual (ej: Oro IV, Platino II).
  * Indicador de racha (si viene de victorias o derrotas consecutivas).

### 5. Perfil de Invocador
* **Comando**: `/perfil [invocador]` o `!perfil [invocador]`
* **Salida**: Nivel de cuenta, liga/división en SoloQ y Flex, porcentaje de victorias (WR) y top 3 campeones con mayor maestría.
