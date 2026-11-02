# Espacios privados y compartidos

Cada usuario conserva su espacio personal. En **Configuración → Espacios** puede
crear otros espacios compartidos, invitar a otros usuarios y compartir cuentas o
activos sin copiarlos.

## Crear y seleccionar un espacio

1. Abre **Configuración → Espacios**. Usa el selector para elegir qué espacio
   estás configurando. Pulsa **Crear espacio** e introduce su nombre en la ventana.
2. Se creará vacío, usando la moneda de referencia del espacio actual.
3. Crea una invitación indicando el correo de otro usuario y sus permisos.
4. Envía el código que aparece por un canal privado. Finanzr no envía un correo
   automáticamente. El código caduca a los siete días.
5. El destinatario inicia sesión con ese correo y pulsa **Unirse a espacio** en
   esa pantalla. Introduce el código en la ventana para aceptar la invitación.
   Cada invitación se utiliza una sola vez.

Los distintivos indican quién puede acceder al espacio: **Privado**, en verde,
cuando solo tiene un miembro; **Compartido**, en azul, cuando tiene más de uno.
Una invitación pendiente no cambia el distintivo. Si sale el último miembro
adicional, el espacio vuelve a mostrarse como privado.

Cuando perteneces a varios espacios, el selector de la barra lateral permite
alternar entre ellos. Cada resumen y sección muestra solo los datos visibles en
el espacio seleccionado.

## Compartir sin duplicar gestiones

En **Compartir cuentas y activos**, el espacio seleccionado arriba es el destino.
La columna izquierda muestra tus cuentas y activos disponibles de otros espacios
que administras. Pulsa un elemento para compartirlo: aparecerá en la columna derecha.
**Compartir todo** añade de una vez todos los elementos que faltan, sin duplicar los
que ya están incluidos. El buscador filtra ambas listas; compartir todo incluye
todos los disponibles, aunque el buscador oculte alguno.

Elige **Solo lectura** o **Puede editar** antes de añadir elementos. Puedes cambiar
el permiso de cada elemento propio desde la columna derecha. La flecha hacia la
izquierda revoca el acceso y devuelve el elemento a la lista de disponibles.
Los elementos del propio espacio y los compartidos por otros miembros se muestran
identificados, sin permitir retirar recursos ajenos.

Debes ser propietario del espacio original y propietario o editor del destino.
Cada elemento se valida por separado: si alguno falla al compartir todo, se
indican los que ya se han compartido y se actualizan las listas antes de reintentar.

La cuenta o el activo mantiene su registro original. Una cuenta compartida incluye
todas sus posiciones, su historial completo y los movimientos futuros. Las
importaciones, movimientos y saldos se gestionan una sola vez y se reflejan en
ambos espacios. No se comparte el resto del patrimonio del propietario.

Los permisos de edición permiten mantener el registro y sus movimientos, pero no
eliminar el activo original desde el destino ni cambiar ajustes de mercado de su
espacio propietario. Las correcciones manuales de precios, splits o divisas se
gestionan desde el espacio original y se utilizan al valorar las posiciones
compartidas. Los elementos manuales e inmobiliarios se comparten individualmente.

Ambos espacios deben usar la misma moneda de referencia. Si se reúnen posiciones
del mismo instrumento procedentes de varios propietarios, sus ajustes de mercado
deben ser compatibles; si difieren, Finanzr solicita resolver el conflicto en vez
de mezclar valoraciones.

## Miembros y acceso

- **Propietario:** gestiona miembros, invitaciones, nombre y archivo del espacio.
- **Editor:** añade y mantiene datos. En elementos ajenos compartidos, también
  necesita que el permiso del elemento permita editar.
- **Lector:** consulta datos y puede salir del espacio.

Puede haber varios propietarios. Antes de que salga el último o cambie su rol,
debe nombrar a otro. Un espacio personal no admite invitaciones.

**Revocar acceso** conserva el activo original y lo retira del espacio de destino.
Archivar un espacio compartido lo oculta para todos sus miembros; no elimina los
activos que otras personas compartieron desde sus espacios personales.
