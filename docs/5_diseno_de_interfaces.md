# Diseño de interfaces de Academia TM

## 1. Alcance y principios

Este documento define la presentación, navegación, componentes, identidad visual e interacción de la administración y el portal de Academia TM. Contiene las decisiones necesarias para diseñar las pantallas del sistema completo, independientemente del avance de implementación. Las medidas, colores y recorridos se aplican como una única especificación, sin alternativas de composición.

La aplicación conserva Django Templates, formularios del servidor, CSS semántico y JavaScript por funcionalidad. La interfaz no introduce un framework visual, una SPA, un router cliente ni una segunda familia de iconos. Los permisos y las reglas comerciales se verifican en el servidor; la presentación comunica su resultado.

### 1.1 Lectura y divulgación progresiva

La pantalla de detalle comienza con identidad, contexto, estado y datos. Los formularios y campos editables se renderizan cuando se solicita una acción. «Editar», «Registrar», «Responder» o un menú «Acciones» actúan como disparadores explícitos.

Hay una sola operación de escritura abierta por contexto. Mientras se edita una ficha se ocultan sus otras acciones de escritura. Guardar confirma la operación; Cancelar restituye lectura y foco al disparador sin persistir cambios. Volver a editar conserva los datos de la revisión. Cerrar un panel o un modal no confirma una escritura.

Las colecciones usan filas compactas con estado y una única entrada de acción por elemento, que revela las opciones de esa fila. No se repiten formularios, selectores ni tarjetas de edición completas por persona. Con una, diez o cincuenta personas se conserva el mismo patrón. Sólo una fila tiene un editor abierto; el resto permanece informativo.

Las acciones se muestran cuando corresponden al estado y al permiso. Una acción que no aplica se oculta; se usa un control deshabilitado únicamente cuando explicar el impedimento ayuda a completar la tarea. Los datos de sólo lectura mantienen contraste de texto activo.

Un vacío presenta una frase breve y, si existe una acción autorizada, un único disparador. Un resultado sin coincidencias ofrece Limpiar filtros. Un error de consulta no se presenta como ausencia de registros.

### 1.2 Lenguaje y significado

Se usa español con voseo: «Seleccioná una sede», «Revisá los cambios», «Ingresá el motivo». Los nombres de módulos, etiquetas y estados son nominales. Los botones nombran la operación concreta y evitan «Aceptar» como confirmación genérica de una escritura; Aceptar se reserva también para la decisión del invitado cuando ésa es la acción.

Se distinguen planes de clases, membresías de socios, contrataciones y reservas de cancha. Ser socio es una condición comercial, no un rol de permisos. Contratar, asignar a clases y cobrar son operaciones separadas. Anular, finalizar, desactivar, retirar, rechazar, quitar una celda y registrar una devolución tienen etiquetas distintas.

No se presentan deuda, excedente, sobrepago, pendiente de pago ni estado de pago calculados. Un importe aplicado no acredita dinero recibido; un cobro no confirma asistencia, participación o realización.

Fechas: `dd/mm/aaaa`; meses: «Noviembre de 2026»; horas: `HH:mm–HH:mm`; importes: ARS con dos decimales y alineación a la derecha. Toda fecha, corte y presentación temporal utiliza `America/Argentina/Salta` y el reloj del servidor.

## 2. Arquitectura y navegación

### 2.1 Audiencias

La administración y el portal son interfaces del mismo sistema. La cuenta administrativa tiene navegación exclusiva; no se ofrece un selector de rol ni un conmutador entre ambas áreas. Los enlaces se construyen según permisos vigentes y nunca sustituyen la autorización de las rutas.

Las dos áreas comparten identidad, cabecera, componentes, escalas y reglas de lectura y edición. La navegación cambia según la cantidad y naturaleza de sus destinos.

### 2.2 Administración

La administración utiliza una cabecera y un lateral de grupos visibles. Los encabezados de grupo sólo tienen texto; todos los enlaces del lateral tienen icono Iconoir y texto.

| Grupo | Destino | Contenido y profundidad local | Icono |
|---|---|---|---|
| Entrada | Inicio | Pantalla de entrada y accesos autorizados existentes | `home-simple-door` |
| Operación | Agenda | Día, Semana, búsqueda, disponibilidad, turnos, historial y acciones del día o del mes | `calendar` |
| Operación | Clases | Planilla semanal, generación y consultas de clases | `tennis-ball` |
| Operación | Usuarios | Lista, inspector, ficha y actividad de clases o reservas de una persona | `group` |
| Membresías | Contrataciones | Altas, renovaciones, consulta y anulación de planes o membresías | `clipboard-check` |
| Membresías | Planes | Catálogo de planes de clases | `book` |
| Membresías | Membresías de socios | Catálogo de productos para socios | `credit-card` |
| Membresías | Caja | Sesión, movimientos e historial | `wallet` |
| Configuración | Sedes y canchas | Sede, canchas, horarios y tarifa | `building` |
| Configuración | Feriados | Consulta, registro, revisión y retiro de feriados | `calendar-minus` |
| Consulta transversal | Auditoría | Cambios e intentos rechazados, de sólo lectura | `journal` |

Contrataciones ofrece filtros de tipo, titular, producto, mes y estado. El seguimiento de personas sin contratación se consulta desde la plantilla semanal. La ficha de un registro no agrega un tercer nivel permanente de enlaces al lateral. Los grupos no son pantallas ni nuevos módulos de negocio.

La cabecera identifica Academia TM y Administración. Ofrece Cuenta, con Mi perfil, Cambiar mi contraseña y Cerrar sesión, y el control de modo visual. Las migas muestran los niveles reales del recorrido, sin repetir enlaces al registro actual.

### 2.3 Portal

El portal utiliza navegación superior con texto, sin lateral ni iconos en sus enlaces, pestañas, Cuenta o cambio de tema:

```text
Academia TM | Inicio | Agenda | Mi actividad | Mis contrataciones | Oferta | Cuenta
```

| Destino | Organización del contenido |
|---|---|
| Inicio | Pantalla de entrada existente, con los componentes y temas compartidos |
| Agenda | Disponibilidad, creación de reserva y consulta de actividades autorizadas |
| Mi actividad | Pestañas Clases y Reservas; cada una conserva su contexto de consulta |
| Mis contrataciones | Planes y membresías propios; contratar membresía o renovar el mismo plan bajo demanda |
| Oferta | Pestañas Planes, Membresías y Tarifas |
| Cuenta | Perfil propio, cambio de contraseña y cierre de sesión |

Inicio conserva su función de entrada; no incorpora indicadores, gráficos, prioridades automáticas ni una composición adicional de dashboard. Los recorridos del sistema son accesibles desde sus destinos de navegación.

Mi actividad es visible para cualquier rol del portal. Clases no exige Alumno. Reservas exige el rol Reservas vigente; un vínculo histórico de invitación no evita ese requisito. Oferta exige autenticación y Público; no es un catálogo anónimo. Mis contrataciones corresponde al titular autenticado y ofrece las operaciones propias de §10, sin exigir Alumno para una membresía.

Las pestañas están dentro de la página y no agregan otra cabecera de aplicación. El panel activo se identifica visual y programáticamente; los paneles ocultos no contienen controles alcanzables con teclado. Cambiar de pestaña no confirma ni descarta silenciosamente una edición.

Sin sesión se ofrecen Ingresá, Creá tu cuenta, Recuperá tu contraseña y la consulta acotada de horarios generales por sede. La consulta de horarios no revela precios ni representa disponibilidad de una cancha.

## 3. Layout, tipografía y dimensiones

Las dimensiones son referencias de escritorio en CSS px. Tipografía, espacios, radios y controles se expresan en rem con base de 16 px; los anchos de contenido son flexibles con máximos. Bordes y geometría de Agenda se expresan en px.

| Elemento | Medida |
|---|---|
| Cabecera compartida | 64 px |
| Lateral administrativo | 224 px |
| Margen lateral del contenido | 24 px por lado |
| Inspector de listados | 280 px totales, incluidos borde y padding |
| Separación lista e inspector | 24 px |
| Panel de Agenda | 400 px |
| Separación grilla y panel de Agenda | 20 px |
| Fila mínima administrativa | 44 px; crece con el contenido |
| Fila mínima del portal | 48 px; crece con el contenido |
| Control normal | 40 px de alto como mínimo |
| Control compacto | 32 × 32 px como mínimo |
| Formulario general | Máximo de 760 px |
| Formulario de acceso | Máximo de 560 px |
| Radios | 8 px en controles; 12 px en tarjetas e inspectores; 16 px en modales |
| Escala de espaciado | 4, 8, 12, 16, 24, 32 y 48 px |
| Separación etiqueta/campo | 8 px |
| Campos relacionados | 16 px |
| Secciones | 24 o 32 px |

Los máximos de formulario no limitan grillas ni listados. Las tarjetas y fichas no usan sombras para establecer jerarquía; se organizan mediante espacio, tipografía, superficies y bordes. El overlay de un modal separa la tarea del fondo inerte.

| Función | Tipografía | Tamaño/interlineado | Peso |
|---|---|---|---|
| Título de página | Anybody | 28/36 px | 600 |
| Sección y horario destacado fuera de Agenda | Anybody | 20/28 px | 600 |
| Contenido, campos y botones | Atkinson Hyperlegible Next | 16/24 px | 400; etiquetas y botones 600 |
| Ayuda y encabezado de tabla | Atkinson Hyperlegible Next | 14/20 px | 400 o 600 según función |

Poppins Bold es sustituta de Anybody y Liberation Sans de Atkinson Hyperlegible Next si falla la carga. Se cargan las fuentes reales; las sustitutas no definen otra identidad. Las horas de Agenda usan Anybody conservando su tamaño, interlineado y caja.

El texto y las etiquetas se alinean a la izquierda; los importes, a la derecha. Los nombres largos ajustan líneas sin recortar información esencial ni ensanchar automáticamente el inspector. Los metadatos extensos se consultan en la ficha completa.

### 3.1 Adaptación y ampliación

Las referencias de escritorio son 1280, 1440 y 1920 px. Cabecera y navegación redistribuyen sus elementos cuando el ancho útil o el zoom lo requiere; no se ocultan destinos sin otro acceso ni se cambia la escala de tipografía por audiencia.

El inspector pasa debajo de la lista cuando no cabe manteniendo un área de lectura útil. El panel de Agenda también pasa debajo de la grilla cuando no cabe junto a ella. La grilla conserva desplazamiento horizontal propio y columnas legibles; el resto de la página redistribuye contenido sin desplazamiento bidimensional generalizado.

## 4. Identidad visual y temas

Claro y oscuro cubren todas las pantallas, campos, selectores nativos, modales, mensajes, estados, navegación, Agenda y comprobantes. La preferencia explícita se conserva en el navegador, se aplica antes de mostrar el contenido y se comparte entre pestañas del mismo origen. Sin elección se utiliza la preferencia del sistema y se siguen sus cambios. Si el navegador impide guardar preferencias, el cambio sigue funcionando en la página abierta. El control nombra el destino: Modo oscuro o Modo claro. El tema no cambia permisos, datos ni significado de los estados y no invierte imágenes.

### 4.1 Colores generales

Cada fila define un uso semántico. Los colores no se combinan libremente por semejanza visual.

| Token | Hex | Aplicación |
|---|---|---|
| Violeta principal | `#4B176D` | Acción, enlace, selección y foco en superficies claras |
| Violeta profundo | `#391052` | Hover/pressed primario claro y texto de clase clara |
| Violeta de marca | `#6D3B8D` | Marca y borde de clase clara |
| Violeta suave | `#F0E7F7` | Fondo de clase clara |
| Verde lima | `#B6D532` | Próximo/destacado y foco sobre oscuro |
| Lima oscuro | `#A4C222` | Hover/pressed destacado claro |
| Lima suave | `#F1F6DA` | Fondo de destacado en claro |
| Verde oliva | `#283400` | Texto sobre lima y borde del botón destacado claro |
| Arcilla | `#9B4F32` | Borde y señal de reserva clara |
| Arcilla oscura | `#7C3C25` | Texto de reserva clara |
| Arcilla suave | `#F7ECE5` | Fondo de reserva clara |
| Fondo tiza | `#F8F6F0` | Fondo general claro |
| Blanco | `#FFFFFF` | Superficie clara y texto principal oscuro |
| Gris lavanda | `#F0EDF2` | Filtros, bloques y encabezados claros |
| Tinta ciruela | `#23192A` | Texto principal claro y texto sobre primario oscuro |
| Gris ciruela | `#6B6072` | Texto secundario, ayudas e iconos base claros |
| Gris malva | `#776C7E` | Placeholder claro sobre campo blanco |
| Lavanda clara | `#DDD3E5` | Texto secundario oscuro |
| Lavanda perla | `#DED7E3` | Separador claro decorativo |
| Malva grisáceo | `#8A7D95` | Borde de control en ambos modos |
| Gris humo | `#EAE6ED` | Fondo no disponible/deshabilitado claro |
| Ciruela apagado | `#6C6275` | Texto no disponible/deshabilitado claro |
| Fondo noche | `#1C0F26` | Fondo general oscuro |
| Superficie | `#291334` | Tarjetas, campos, modales y lateral nocturno |
| Superficie elevada | `#351E43` | Filtros, bloques y encabezados oscuros |
| Ayuda oscura | `#B8ACC2` | Ayudas, placeholder e iconos base oscuros |
| Separador oscuro | `#46325A` | Líneas decorativas oscuras |
| Violeta claro | `#C9A2E8` | Primario, enlace y selección sobre oscuro |
| Violeta claro hover | `#D7B6EF` | Hover del primario oscuro |
| Violeta claro pressed | `#B98AD9` | Pulsación del primario oscuro |

Overlay claro: Tinta ciruela al 40%. Overlay oscuro: Fondo noche al 72%. El modal es opaco; la transparencia se aplica al fondo inerte y no a su texto.

### 4.2 Estados semánticos

| Estado visual | Texto claro | Fondo claro | Borde claro | Texto oscuro | Fondo oscuro | Borde oscuro |
|---|---|---|---|---|---|---|
| Éxito | `#24634A` | `#E8F3EB` | `#B6D5C1` | `#8FD1AE` | `#12281D` | `#2F6B4C` |
| Advertencia | `#805212` | `#FFF2D8` | `#E9D0A0` | `#F0C46E` | `#33250B` | `#7A5A1E` |
| Error | `#AB3434` | `#FBECEC` | `#E8B7B7` | `#F29A9A` | `#351617` | `#7E3434` |
| Información | `#245F6B` | `#EAF3F5` | `#BFD8DE` | `#8CCBD8` | `#10282E` | `#2F6672` |
| Inactivo | `#655B70` | `#ECE8F0` | `#D5CDDE` | `#C0B5CC` | `#2E2438` | `#4F4360` |

Los bordes de esta tabla son decorativos. No se usan como única señal ni como límite identificador de un campo. En un campo inválido se conserva el borde de control o se usa el color de texto Error del modo, acompañado por mensaje.

| Significado del dato | Presentación |
|---|---|
| Programada; respuesta Pendiente; Sin respuesta | Neutra, con su etiqueta literal |
| Finalizada | Información, check y texto; no significa pago ni asistencia |
| Anulada | Inactivo, X y texto |
| Activo; Presente; respuesta afirmativa | Éxito y texto; check cuando corresponda |
| Inactivo; Vencido | Inactivo y texto; Vencido no lleva X de anulación |
| Ausente; Sin registrar | Neutros con etiquetas distintas |
| Respuesta negativa; invitación retirada | Inactivo con la etiqueta correspondiente; no son estados de la reserva |
| Caja Abierta/Cerrada; movimiento Vigente | Neutros; no implican acreditación ni pago completo |
| Realizada/No realizada | Resultado de uso con su etiqueta, separado de Finalizada; sin inferir asistencia individual |

### 4.3 Superficies y componentes por modo

| Componente | Claro | Oscuro |
|---|---|---|
| Cabecera | Blanco, Tinta ciruela y Gris ciruela | Superficie, Blanco y Lavanda clara |
| Lateral administrativo | Superficie, Blanco/Lavanda clara y selección Violeta claro | Misma composición nocturna |
| Lista, ficha, inspector y tarjeta | Blanco con texto principal/secundario claro | Superficie con texto principal/secundario oscuro |
| Filtros y encabezados | Gris lavanda | Superficie elevada |
| Campos y selectores | Blanco, borde Malva grisáceo | Superficie, borde Malva grisáceo |
| Grupo de formulario | Gris lavanda con campos blancos | Superficie elevada con campos Superficie |
| Pestañas | Indicador y texto activo Violeta principal | Indicador y texto activo Violeta claro |
| Primario | Blanco sobre Violeta principal; interacción Violeta profundo | Tinta ciruela sobre Violeta claro; variantes hover/pressed |
| Secundario | Blanco, texto/borde Violeta principal | Superficie, texto/borde Violeta claro; hover Superficie elevada |
| Peligro | Par Error claro | Par Error oscuro |
| Destacado | Lima o Lima suave con Oliva | Borde Lima sobre Superficie o Superficie elevada, texto Blanco/Lavanda |
| Deshabilitado real | Gris humo/Ciruela apagado | Fondo Inactivo con texto Malva grisáceo |
| Documento impreso | Blanco con tinta | La impresión conserva la composición clara |

La selección de un enlace o pestaña se indica con texto/indicador además del color. Los enlaces de contenido se subrayan. Hover de secundario o peligro refuerza el texto sin reducir su opacidad. No se aplican grandes rellenos lima en oscuro; Ahora es la excepción de relleno lima y texto oliva en ambos modos.

### 4.4 Contraste y foco

El texto normal, ayudas y placeholders requieren al menos 4,5:1; texto grande, 3:1. Los límites e indicadores necesarios para operar controles requieren 3:1 contra el color adyacente. Los separadores decorativos no sustituyen bordes de controles.

| Par autorizado | Relación |
|---|---:|
| Tinta ciruela / Blanco, Tiza y Gris lavanda | 16,88 / 15,62 / 14,55 |
| Gris ciruela / Blanco, Tiza y Gris lavanda | 5,93 / 5,49 / 5,11 |
| Violeta principal / Blanco, Tiza y Gris lavanda | 12,78 / 11,83 / 11,02 |
| Gris malva / Blanco | 4,96 |
| Blanco / Noche, Superficie y Elevada | 18,33 / 16,98 / 14,81 |
| Lavanda clara / Noche, Superficie y Elevada | 12,68 / 11,74 / 10,24 |
| Ayuda oscura / Noche, Superficie y Elevada | 8,48 / 7,86 / 6,85 |
| Violeta claro / Noche, Superficie y Elevada | 8,57 / 7,94 / 6,92 |
| Tinta ciruela / Violeta claro, hover y pressed | 7,89 / 9,51 / 6,19 |
| Blanco / Violeta profundo | 15,33 |
| Oliva / Lima, Lima oscuro y Lima suave | 7,94 / 6,52 / 11,97 |
| Borde de control / Blanco, Tiza y Gris lavanda | 3,85 / 3,57 / 3,32 |
| Borde de control / Superficie y Elevada | 4,40 / 3,84 |
| Texto Error / Blanco y Gris lavanda | 6,42 / 5,53 |
| Texto Error oscuro / Superficie y Elevada | 7,97 / 6,96 |
| Texto/fondo Éxito, Advertencia, Error, Información e Inactivo claros | 6,24 / 6,05 / 5,60 / 6,37 / 5,29 |
| Texto/fondo Éxito, Advertencia, Error, Información e Inactivo oscuros | 8,83 / 9,10 / 7,72 / 8,53 / 7,52 |

Las relaciones se calculan con luminancia relativa sRGB y se expresan como `n:1`; la tabla omite el sufijo por legibilidad. Para cada canal normalizado se usa `c/12,92` si `c ≤ 0,04045` y `((c + 0,055)/1,055)^2,4` en otro caso. Luminancia: `0,2126 R + 0,7152 G + 0,0722 B`. Contraste: `(L mayor + 0,05)/(L menor + 0,05)`. La decisión usa el valor sin redondear.

El foco fuera de Agenda es un contorno continuo de 2 px separado 2 px del relleno. Se usa Violeta principal sobre claro y Lima sobre oscuro, incluido el lateral nocturno del tema claro. En Agenda se conservan los grosores y offsets propios. El anillo no queda pegado a un botón de luminosidad similar.

Lima como texto sobre blanco, Perla como texto y los separadores oscuros no alcanzan contraste de lectura y no se usan para ese propósito. El deshabilitado oscuro tiene 3,82:1 y su exención sólo aplica a un control realmente deshabilitado. El texto de lectura, incluidos datos históricos, no recibe esa exención.

### 4.5 Iconografía

Se utiliza Iconoir Regular, trazo de 2 px, tamaño de 20 px en campos y 24 px en navegación. Los identificadores de destinos están definidos en §2.2. En contenido se conservan los conceptos Usuario, Contraseña, Ver contraseña, Menú, Flecha, Flecha de lista, Reloj, Confirmación y Anulación.

Se usa la marca gráfica de Academia TM con proporción conservada y sin filtros de inversión; la identidad corresponde a tenis. Los iconos decorativos se excluyen del árbol accesible; el texto aporta el nombre de la acción. Un botón que sólo tiene icono lleva un nombre accesible contextual. Selección usa Violeta principal en claro y Violeta claro en oscuro; iconos base usan el texto secundario correspondiente. Los estados conservan sus colores semánticos.

## 5. Componentes e interacción compartidos

### 5.1 Lista e inspector

Los listados presentan búsqueda, filtros bajo demanda, resumen de criterios aplicados, resultados y paginación. Se utilizan 25 registros por página en usuarios, catálogos, oferta, contrataciones y auditoría. No se añaden ordenamiento cliente de una página parcial, exportaciones, favoritos ni selección masiva de registros sin una operación funcional definida.

Cada fila tiene una entrada compacta para consultar el registro. Seleccionarla abre un inspector no modal de 280 px. La lista conserva filtros, página, posición y selección; cerrar devuelve foco a la fila. El inspector contiene identidad, estado, datos principales, acceso a ficha completa y acciones reveladas por disparador. No abre un editor por seleccionar.

La ficha completa se utiliza cuando la información o tarea requiere más ancho. El retorno restituye contexto de la lista. Cambiar página o filtros cierra una selección que ya no pertenece al resultado; si una operación hace que el registro deje de cumplir el filtro, se anuncia el resultado y se vuelve al encabezado de resultados.

### 5.2 Fichas y edición

Las fichas ordenan identidad y estado, datos principales, relaciones o actividad y metadatos secundarios. Se usan etiquetas/valores semánticos, secciones y expansión de historia. Los datos opcionales se omiten cuando no aportan o se indican con una frase breve, sin campos vacíos de formulario.

La acción abre una región con título específico, datos de referencia, campos permitidos y Guardar cambios/Cancelar. El editor general mide hasta 760 px y ocupa el eje principal sin inspector simultáneo. Los nombres de acciones incluyen la entidad: Editar correo, Editar producto o Gestionar invitados.

### 5.3 Formularios, selectores y errores

Cada campo tiene etiqueta persistente. Ayudas y formatos se muestran junto al campo y no dependen de un tooltip. Las observaciones opcionales se revelan mediante su disparador. Un placeholder sirve como ejemplo y no reemplaza una etiqueta.

Un error de envío presenta resumen enfocado con enlaces a campos o filas, mensajes específicos y conservación de los datos no sensibles. Si cambió la versión revisada, se muestran los datos vigentes y se exige revisar antes de confirmar. No se sobrescribe una decisión que el actor no revisó.

Los selectores de personas comparten búsqueda remota, espera breve para evitar solicitudes por cada pulsación, cancelación de solicitudes reemplazadas, descarte de respuestas atrasadas y resultados compactos. Se opera con teclado y se anuncian carga, cantidad, vacío, error y selección. No se crean usuarios dentro de reservar, contratar o asignar. Los candidatos excluidos por autorización no se exponen para explicar una validación; si una selección deja de ser elegible se informa sobre ella sin revelar una nómina de terceros.

| Estado de candidato a invitado | Presentación y operación |
|---|---|
| No elegible | Motivo junto al resultado: cuenta inactiva, rol insuficiente, organizador o duplicado; sin Agregar |
| Cupo completo | Explica el límite de dos Programadas por persona; impide incorporar |
| Coincidencia personal | Explica la incompatibilidad de horario con otra actividad sin revelar datos ajenos; impide incorporar |
| Elegible | Nombre y condición comercial autorizada; una acción compacta Agregar |

Los impedimentos usan Error y texto; no existe una confirmación que permita ignorarlos. No tener membresía no es un impedimento personal: en una reserva con membresía genera adicional. El selector no responde por el invitado.

### 5.4 Confirmaciones y revisión

Cada contexto tiene una acción principal; los disparadores de detalle y las alternativas son secundarios. Las confirmaciones identifican entidad, selección y efecto. Durante el envío se anuncia espera y se evita duplicar la operación. Sólo se comunica éxito cuando el servidor confirma la escritura completa.

| Operación | Lugar de revisión |
|---|---|
| Desactivar sede o cancha | Página completa con eventos futuros afectados e impedimentos |
| Registrar feriado que anula clases futuras | Página completa con fecha y clases afectadas |
| Generar clases | Página completa con candidatas, omisiones y dos confirmaciones explícitas de irreversibilidad |
| Anular contratación | Página completa con titular, producto, período, motivo y condiciones comerciales |
| Anular movimiento | Página completa con sesión de origen, motivo y efecto sobre efectivo |
| Cerrar caja | Página completa con resumen, esperado, contado, diferencia y motivo |
| Acciones del día o mes y bloqueos en lote | Panel de Agenda, con selección, vista previa y confirmación |
| Crear reserva o clase desde Agenda | Resumen en el panel y confirmación contextual |
| Actualizar socios y gestionar invitados | Revisión contextual de cambios y total antes de confirmar |
| Asistencia | Editor compacto y guardado conjunto, sin revisión adicional |

Las revisiones de página completa se abren al solicitar la operación, nunca al visitar un detalle. Ofrecen Volver a editar y Confirmar con el nombre de la acción. Una revisión que pierde vigencia o cambia de conjunto vuelve a la revisión y no ejecuta un alcance distinto.

### 5.5 Modales, menús y mensajes

Los modales tienen título, fondo inerte, foco interno, recorrido de Tab contenido y retorno al disparador. Escape cancela cuando la operación lo permite; nunca confirma. Los inspectores y paneles de lectura son no modales y no atrapan foco. Los menús de acciones se abren explícitamente, admiten teclado y Escape devuelve foco a su disparador.

Carga conserva contexto y anuncia actualización. Error conserva criterios y ofrece reintentar; sin resultados no simula registros. Una respuesta vieja no reemplaza una selección nueva. Los avisos de éxito son breves y no ocultan el estado resultante; errores y consecuencias necesarias permanecen disponibles. Los avisos con autocierre se pausan por foco, interacción o pestaña no visible.

## 6. Agenda y disponibilidad

### 6.1 Organización de consulta

Agenda es la entrada única para crear reservas, clases concretas y bloqueos. Mi actividad y la actividad de una persona son consultas y no duplican el alta. La pantalla sitúa sede, vista y fecha antes de la grilla y mantiene acciones administrativas fuera de las celdas.

Día muestra todas las canchas de una sede en columnas y horas en filas. Semana muestra una cancha, lunes a domingo en columnas y horas en filas; el selector de cancha aparece en esa vista. Anterior, Siguiente y Hoy conservan sede y contexto. Una semana que cruza los límites de calendario mantiene sus columnas y deja sin acciones las fechas fuera del rango.

Seleccionar un turno actualiza sólo el panel y el resaltado sin recargar ni desplazar la grilla. Cambiar sede limpia cancha y turno. Cerrar o volver dentro del panel mantiene la selección pertinente. Ante un error se conserva el último detalle válido y sólo se aplica la respuesta de la selección vigente.

Buscar registros revela filtros sobre la consulta, cerrados por defecto. Administración busca reservas por número, organizador, sede, cancha, fecha y estado, y clases por los criterios de profesor y estado. El portal limita resultados y criterios a sus relaciones autorizadas. Los resultados son filas que conducen al registro o turno, sin sustituir la ocupación de la grilla.

Consultar disponibilidad es administrativo: sede, fecha, inicio y cancha opcional. Devuelve las canchas disponibles para una hora, sin registrar turnos ni eventos ni exigir tarifa normal. Crear una reserva sigue requiriendo seleccionar y revisar el turno en Agenda.

### 6.2 Geometría y ancho

La columna de horas mide 58 px, cada cancha tiene mínimo de 120 px y las celdas conservan altura de referencia de 66 px. La tabla tiene ancho mínimo `max(300px, N × 120px + 58px)`. Se conserva el padding, bordes de 1 px, alturas, offsets y distribución interna de las celdas; la escala general no los modifica por cascada. No se agregan barras laterales de color ni filas para estados.

Con cinco canchas el mínimo de tabla es 658 px. El cálculo de escritorio, descontando márgenes, lateral y panel, es:

| Ancho de ventana | Contenido administrativo | Ancho para tabla administrativa | Contenido portal | Ancho para tabla portal |
|---:|---:|---:|---:|---:|
| 1280 px | 1008 px | 588 px | 1232 px | 812 px |
| 1440 px | 1168 px | 748 px | 1392 px | 972 px |
| 1920 px | 1648 px | 1228 px | 1872 px | 1452 px |

La tabla usa scroll propio si el espacio es menor a su mínimo; no estrecha las columnas para evitarlo. Las cifras son referencias de layout, no mediciones de una implementación renderizada. El inspector de listado no se agrega al lado del panel de Agenda.

### 6.3 Celdas, estado e historial

El tipo de actividad se expresa por fondo y rótulo, conservado al seleccionar, finalizar o anular. El estado se indica por texto e icono independiente. La celda muestra el estado en la esquina superior derecha y, si existen anulaciones accesibles, un indicador `calendar-minus` en la inferior derecha, sin cantidad, fondo propio ni acción independiente.

Seleccionar el turno permite abrir Ver eventos anulados dentro del panel. El listado muestra horario, cancha y enlace para volver; ordena por momento de anulación descendente. Cada fila conserva el fondo del tipo y enlaza al detalle autorizado. Destaca el tipo antes del organizador o motivo clasificado de bloqueo. No expone en ese listado motivo libre de anulación, identificadores internos ni responsable o momento de anulación.

Las clases muestran el primer profesor activo y la cantidad restante `+N`, ordenados por identificador; el grupo completo se consulta en el detalle autorizado. Ahora aparece sólo en el margen horario y no dibuja una línea que atraviese eventos. Hoy se destaca en el encabezado sin usar fondo de clase.

Las pausas comunes se conservan y una actividad histórica fuera de las franjas vigentes mantiene su fila. Un día sin horarios ni eventos tiene un vacío informativo. Instalaciones inactivas permiten historia sin nuevas actividades. El portal oculta filas iniciadas sin actividad propia ni historial accesible y conserva completas las filas necesarias para consultar lo propio; el resto de sus celdas mantiene privacidad.

### 6.4 Privacidad y calendario de consulta

Administración consulta toda la ocupación. El portal sólo conoce actividades autorizadas por su vínculo. Una celda ajena dice No disponible, con fondo liso y sin tipo, patrón de bloqueo, identificador, nombres, observaciones o importe. Su panel sólo informa sede, cancha, fecha y horario.

La historia comienza el 01/08/2026 y Agenda consulta hasta un año calendario después de hoy. Las altas de eventos tienen inicio futuro y llegan como máximo al último día del segundo mes calendario siguiente; las reservas tienen además la ventana específica de §7.1. Las consultas de actividad y usos admiten hasta 366 días inclusivos; un rango mayor se consulta por tramos.

### 6.5 Apariencia de la grilla

| Elemento | Texto y fondo claro | Texto y fondo oscuro | Borde o señal |
|---|---|---|---|
| Encabezados y horas | Tinta ciruela / Gris lavanda | Lavanda clara / Superficie elevada | Líneas decorativas |
| Libre | Tinta ciruela / Blanco | Blanco / Superficie | Hover Gris lavanda/Elevada |
| Clase | Violeta profundo / Violeta suave | `#EADCF5` / `#3A2150` | Violeta de marca / `#9367B9` |
| Reserva | Arcilla oscura / Arcilla suave | `#F2CDBB` / `#40241A` | Arcilla / `#B0603F` |
| Bloqueo administrativo | `#574C63` / fondo Inactivo claro | Texto/fondo Inactivo oscuro | Rayado con el borde Inactivo del modo |
| No disponible del portal | Ciruela apagado / Gris humo | Ayuda oscura / `#241830` | Liso, sin filtrar tipo |
| Pausa y fuera de franja | Fondo tiza | Fondo noche | Sin controles de creación |
| Feriado | Información clara | Información oscura | Etiqueta en la fecha |
| Ahora | Oliva / Lima | Oliva / Lima | Sólo margen horario |

El rayado de bloqueo es diagonal a 135°, en bandas de 4 px, con texto legible sobre ambos colores. Las líneas de grilla usan Perla o Separador oscuro y son decorativas. El borde de tipo no sustituye el foco de selección. Un turno seleccionado conserva contorno de 2 px con offset de −1 px y recupera opacidad 1.

Las relaciones de texto/fondo de clase son 12,76:1 en claro y 10,61:1 en oscuro; reserva, 7,15:1 y 9,58:1. El borde de clase oscuro alcanza 3,23:1 contra el relleno y 3,95:1 contra la superficie; el de reserva, 3,09:1 y 3,71:1. Texto de bloqueo claro alcanza 6,63:1 en base y 5,20:1 en raya; oscuro, 7,52:1 y 4,65:1. Finalizada opaca sobre clase/reserva usa Información con 5,98/6,18:1 en claro y 7,70/7,84:1 en oscuro.

### 6.6 Turnos iniciados

Los turnos iniciados conservan `opacity: .6` sobre Blanco en claro o Superficie en oscuro. Su texto histórico sigue siendo lectura activa. Se componen primero texto y fondo al 60% sobre esa superficie y después se evalúa el contraste. Los hijos, flechas y textos secundarios conservan la variante del tipo; no heredan un gris de menor contraste.

| Variante iniciada | Texto claro | Texto oscuro | Contraste efectivo claro/oscuro |
|---|---|---|---|
| Clase | `#100818` | Texto de clase oscura | 4,67 / 4,84 |
| Reserva | `#1A0803` | `#FFE8DC` | 4,73 / 5,36 |
| Libre en hover | `#100818` | Lavanda clara | 4,77 / 4,63 |
| Cerrado | `#100818` | Lavanda clara | 4,97 / 5,25 |
| No disponible | `#100818` | Lavanda clara | 4,60 / 4,99 |
| Bloqueo, base | `#030103` | Blanco | 5,06 / 6,26 |
| Bloqueo, raya | `#030103` | Blanco | 4,64 / 4,79 |
| Finalizada sobre clase | `#000C11` | `#D8E5F0` | 4,71 / 4,91 |
| Finalizada sobre reserva | `#000C11` | `#D8E5F0` | 4,81 / 4,99 |

Sólo en el bloqueo iniciado claro, la raya utiliza Perla en lugar del borde Inactivo para conservar ese contraste. Seleccionar un turno restaura los colores opacos normales y opacidad 1. El rótulo y los iconos legibles acompañan tipo y estado; no se depende del borde atenuado para identificarlos.

### 6.7 Acciones del turno, del día y del mes

Un turno libre revela Nueva reserva, Crear clase y Crear bloqueo a administración según elegibilidad; el portal sólo recibe las opciones de reserva propias. Sobre clase o reserva se muestran Anular y liberar o Anular y bloquear cuando corresponden; un bloqueo ofrece liberar mediante anulación. La finalización de una reserva terminada también se solicita desde su detalle.

Acciones del día y Acciones del mes se resuelven dentro del panel, conservando grilla, sede, fecha y selección. Cada recorrido revela alcance, todas o varias canchas, franja diaria, tipos conservados y motivo. Al bloquear, el motivo clasificado es clima adverso, torneo o mantenimiento, con observaciones opcionales; ese motivo también explica las anulaciones. Anular y liberar exige motivo libre y un mínimo de 25 caracteres si incluye reservas.

El alcance mensual selecciona un mes completo entre el actual y los dos siguientes, con el mes consultado por defecto si está habilitado y el actual en otro caso. Cambiar mes actualiza el panel sin botón adicional. Sólo ofrece Anular y liberar; no crea bloqueos. El horario se aplica a cada día, respetando la selección de inicio inclusivo y fin opcional; un corte no exacto selecciona desde la hora en punto siguiente.

La vista previa separa acciones, eventos conservados y bloqueos existentes. Los listados son compactos y desplegables, con fecha en el alcance mensual. Las actividades iniciadas, Finalizadas o excluidas se conservan. Las anulaciones administrativas de reservas informan devolución de la hora de membresía, sin selector de consumo ni modificación de cobros.

Volver a editar conserva datos. La confirmación identifica actor, parámetros y conjunto revisado, vence a los quince minutos y revalida acceso, estado, inicio y ocupación. El conjunto completo se confirma en una transacción; un cambio de alcance o un turno que alcanza su inicio exige otra revisión sin efectos parciales.

## 7. Reservas

### 7.1 Creación y modalidades

Una reserva ocupa una hora. Se admite desde hoy hasta el tercer día calendario siguiente inclusive, hasta el último turno habilitado de ese día, siempre con inicio futuro. Cada persona puede integrar como máximo dos reservas con evento Programado, sumando organización e invitaciones vigentes Pendientes o Aceptadas, entre todas las sedes. Un turno terminado sigue contando si el evento continúa Programado.

La disponibilidad personal rechaza coincidencias con otra reserva organizada, invitación vigente Pendiente/Aceptada, participación activa de clase en Asistirá o No asistirá o docencia vigente. Las invitaciones de reserva Rechazadas o retiradas no impiden otra actividad. El aviso No asistirá conserva la ocupación. La ocupación de cancha y la disponibilidad personal son controles diferentes y no se pueden exceptuar con una advertencia.

El recorrido parte del turno libre de Agenda:

| Actor | Inicio del recorrido |
|---|---|
| Portal | El organizador es el titular; no aparece selector de otra persona |
| Administración | Nueva reserva → organizador existente → Continuar |

Con el organizador identificado, se comprueba si es socio para la fecha del turno. Si lo es, se ofrecen Reserva normal y Reserva con membresía; si no lo es, sólo Reserva normal. La modalidad abre su recorrido propio y conserva turno y organizador. No se muestran modalidades administrativas antes de conocer al organizador.

| Modalidad | Contenido del recorrido |
|---|---|
| Normal | Tarifa por turno de sede, invitados opcionales y observaciones opcionales; su identidad no altera la tarifa |
| Con membresía | Contratación del organizador para la fecha, horas mensuales disponibles e identificación de todos los invitados; condición socio/no socio y adicional unitario aplicado |

El recorrido con membresía exige una hora disponible y no exige tarifa normal configurada. El organizador compromete una hora de su cupo y cada invitado con beneficio compromete una hora de invitado desde Pendiente. Aceptar conserva ese compromiso; al inicio consume aun sin respuesta. Sin membresía o con cupo de invitado agotado aplica el mismo adicional, con etiquetas que explican el motivo. En normal no se utilizan horas de ningún participante.

La creación presenta progreso por pasos: organizador cuando lo elige administración, modalidad, invitados y revisión. Dos tarjetas contiguas con fondo violeta oscuro y texto claro resumen el turno: una destaca la cancha y muestra la sede; la otra destaca la hora y muestra la fecha. El organizador se presenta en una tercera tarjeta debajo del turno, con fondo claro y texto violeta. Desde el paso de invitados, la modalidad elegida se presenta en una tarjeta contigua a la del organizador, ambas con fondo violeta claro y texto violeta oscuro. En el paso de modalidad, la tarjeta del organizador ocupa todo el ancho. La selección de modalidad presenta dos opciones contiguas con una explicación y su tarifa o disponibilidad. La opción seleccionada se identifica con un check en la esquina superior derecha y el botón «Siguiente» permite avanzar. Las opciones no disponibles se muestran atenuadas, sin acción y con el motivo visible. Los invitados se agregan mediante un buscador por nombre, apellido o usuario, abierto con un botón circular «+» junto a «Invitados», que cambia a «×» para cerrarlo; el buscador aparece antes de los seleccionados, y se muestran en filas compactas con una acción para quitarlos. Al volver se conservan los invitados y las observaciones.

Los precios se presentan en el resumen: turno, organizador, modalidad, tarifa o membresía aplicada, invitados, adicional unitario cuando corresponda y total. La cantidad participante y el total se derivan de relaciones vigentes Pendientes o Aceptadas; no hay cantidad total declarada ni invitados anónimos en modalidad con membresía.

Atrás conserva datos; Cancelar abandona sin crear. La confirmación revalida cuentas, roles, calendario, instalaciones, cupos, disponibilidad, ocupación, contrataciones e importes bajo bloqueos coordinados. Un precio o cobertura que cambió exige una revisión nueva. No se comunica confirmación antes de guardar evento, reserva e invitados juntos. Después se informa el número y se ofrece comprobante al autorizado. El pago se registra aparte en la sede.

### 7.2 Detalle y gestión de invitados

El detalle prioriza número, turno, ubicación, estado y modalidad. Organizador y administración ven condiciones comerciales y total derivado; los cobros se consultan en una sección separada. Los invitados son filas con nombre, respuesta, condición comercial y una acción compacta cuando corresponde.

Gestionar invitados se revela al organizador o administración sólo en una reserva Programada antes del inicio. El formulario presenta dos pasos, Invitados y Revisar cambios, con el turno en tarjetas oscuras y el organizador y modalidad en tarjetas claras. El botón circular «+» abre el buscador antes de los seleccionados y cambia a «×» para cerrarlo. La revisión presenta filas compactas con nombre, condición comercial cuando aplica y acción Agregar o Retirar, junto al total resultante. Volver conserva la selección y la confirmación aplica el conjunto revisado. Agregar busca cuentas activas con Reservas o Administrador, distintas del organizador y sin duplicados. Retirar y reincorporar conservan identidad y respuesta de la relación. Se revalidan cupo, disponibilidad y condición comercial al incorporar.

Sólo se retiran invitaciones Pendientes o Aceptadas. Las Rechazadas permanecen visibles con su respuesta, sin Retirar ni Reenviar. Una retirada muestra su condición histórica y no permite responder mientras esté retirada. Editar a otro invitado conserva las condiciones comerciales de quienes permanecen.

La revisión muestra participantes y nuevo total con el adicional unitario conservado. Retirar un no socio elimina su adicional incluso dentro de las dos horas. Nada de esto modifica cobros ni horas del organizador. No se editan organizador, modalidad, turno ni precio unitario; cambiar turno requiere cancelar y crear otra reserva.

### 7.3 Actualizar socios

«Actualizar socios» es una acción bajo demanda del organizador o administración, sólo en reservas con membresía Programadas antes del inicio. Revisa membresías que cubren la fecha del turno de los invitados vigentes Pendientes o Aceptados.

La vista previa presenta únicamente los cambios de condición y el total resultante. Si un invitado contrató una membresía después de ser invitado, se acredita como socio y deja de generar adicional, si tiene cobertura y horas de invitado disponibles. Confirmar compromete una hora; sin saldo el adicional se mantiene. Sin cambios se informa que la condición de socios está actualizada, sin simular una modificación.

Confirmar revalida inicio, permisos, relaciones, contrataciones y saldo disponible bajo los bloqueos comunes con invitaciones y ajustes. Si cambió el conjunto revisado se exige otra revisión. Se conserva el adicional unitario original, la historia comercial, respuestas, horas del organizador y cobros. No modifica Rechazadas ni retiradas ni reincorpora personas.

### 7.4 Respuesta del invitado

El invitado titular solicita Responder invitación y elige Aceptar o Rechazar antes del inicio. Después de la primera respuesta puede usar Cambiar respuesta una sola vez, sin volver a Pendiente. El detalle muestra decisión, primera respuesta y disponibilidad del cambio sin abrir controles por defecto.

Rechazar libera hora de invitado comprometida, cupo personal, disponibilidad y adicional; conserva relación e historia. Volver a aceptar revalida disponibilidad, cupo y condición de socio para la fecha; si falta cobertura o saldo de invitado y la reserva utiliza la membresía del organizador, participa con adicional, distinguiendo no socio de cupo agotado, con el importe unitario conservado. La respuesta no cancela la reserva ni devuelve la hora del organizador.

Al comenzar, Pendiente se presenta como Sin respuesta, sin nueva transición almacenada y sin presumir asistencia. Ya no se ofrecen Responder ni Cambiar respuesta. Organizador y administración no responden por el titular y no reinician su único cambio mediante retiros o reincorporaciones.

### 7.5 Cancelación, nueva reserva y resultado

| Operación | Presentación y efecto |
|---|---|
| Cancelación propia | Antes del inicio, motivo libre de al menos 25 caracteres y revisión; más de dos horas libera la hora, dos horas o menos conserva consumo |
| Cancelación administrativa | Causa de la academia y motivo; siempre libera hora y cupo, sin elección de consumo |
| Anulación con bloqueo | Muestra también el bloqueo que ocupará el turno y confirma ambos efectos juntos |
| Finalización manual | Sólo administración y turno terminado, como alternativa a la tarea horaria |
| Resultado de uso | Después de Finalizado, Realizada o No realizada; antes se lee Sin registrar |
| Corrección del resultado | Una sola vez, resultado distinto y motivo obligatorio, sin plazo límite; muestra original y datos de corrección |

Cada organizador gestiona su propia cancelación; administración no se usa como sustituto para evitar el consumo de una cancelación propia tardía. El límite se calcula al confirmar con precisión del servidor, sin redondeo a minutos. Ningún evento iniciado se anula.

Una reserva Anulada conserva su detalle e historia. No muestra acciones de restaurar o reprogramar ni enlaces a un origen o sucesor. Una nueva reserva se inicia por el recorrido habitual de Agenda, incluso para el mismo turno si está disponible. Se seleccionan participantes explícitamente y sus respuestas comienzan Pendientes; se revisan cobertura, cupos y precios para la fecha elegida. Cada reserva conserva sus movimientos y sus horas sin traslados.

La revisión de cancelación informa el efecto por rol: libera siempre las horas comprometidas de invitados; la propia conserva la hora de organizador con dos horas o menos y la libera con más de dos; la administrativa libera ambos roles. La devolución de dinero es una decisión administrativa independiente.

Finalizar no presume realización. No realizada y una corrección del resultado no devuelven horas ni cambian invitados o respuestas. Ninguna cancelación o corrección devuelve dinero automáticamente; las devoluciones se registran como egresos independientes de caja. La reserva Anulada no recibe nuevos ingresos.

### 7.6 Datos del invitado y comprobantes

| Dato o acción | Organizador | Invitado identificado | Administración |
|---|---|---|---|
| Número, fecha, inicio/fin, duración, sede y cancha | Visible | Visible | Visible |
| Estado y fechas operativas | Visible | Visible, sin responsables | Visible |
| Modalidad y relación Organiza/Invitado | Visible | Visible | Visible |
| Nombres y apellidos del organizador y demás invitados registrados | Visible | Visible, sin fallback al nombre de usuario | Visible |
| Cantidad participante | Visible | Visible como cantidad | Visible |
| Condición y contratación de socio propia | Visible | Visible; no muestra cargo adicional ni importe | Visible |
| Condiciones comerciales y contrataciones ajenas | Datos necesarios para gestionar su reserva | Ocultas | Visibles |
| Tarifa, total, adicional e importe aplicado | Visibles | Ocultos | Visibles |
| Cobros y sus datos | Vigentes vinculados a su reserva | Sin acceso ni indicación de existencia/cantidad | Consulta autorizada |
| Contacto, responsables, observaciones y motivo libre de anulación | Sólo los datos propios y operativos autorizados | Ocultos | Visibles según función |
| Cancelar reserva, gestionar invitados y Actualizar socios | Según estado y plazo | Sin acceso | Según operación y estado |
| Responder invitación | No responde por terceros | Su propia decisión y único cambio | No responde por terceros |
| Comprobante, impresión y guardado | Permitidos | Denegados, también por URL directa | Permitidos |

El comprobante acredita la reserva, no el pago. Presenta número, estado, turno, duración, sede, cancha, organizador y los importes aplicados según modalidad. No toma precios vigentes del catálogo para reemplazar los registrados. La vista de pantalla respeta tema; impresión y guardado del navegador usan blanco y tinta. No existe una versión parcial del comprobante para invitados.

## 8. Clases, planilla y asistencia

### 8.1 Planilla semanal

La planilla representa una única semana tipo vigente por sede y no es Agenda ni historial de clases. Se elige sede y cancha; cada celda semanal muestra profesores y participantes previstos. Seleccionar abre lectura; Agregar horario, Editar o Quitar se revelan por acción. Se conserva selección de horarios propia de planilla, sin trasladarla a reservas.

Crear o editar exige al menos un profesor activo con rol Profesor. Los participantes se buscan primero entre Alumno y se puede ampliar a cualquier cuenta activa, sin exigir plan, cobro ni Alumno para participar. No se permite que una persona ocupe ambas funciones en la misma clase.

La plantilla no tiene mes, copias mensuales ni respuestas de participación. Quitar una celda o una persona afecta futuras generaciones y conserva las clases concretas. No se muestran acciones para eliminar físicamente clases generadas.

### 8.2 Generación

Generar clases ofrece un mes completo, con el actual por defecto y sólo el actual y los dos siguientes. El período de generación admite hasta 62 días inclusivos. La revisión muestra candidatas, omisiones y motivos, agrupados en tablas o listas compactas.

Se omiten días pasados, turnos iniciados, feriados, ocupación, instalaciones inactivas, usuarios no habilitados y coincidencias personales con clases o reservas. La candidata se omite completa; no se quitan personas para producir una clase parcial. Las candidatas de la misma ejecución se evalúan en un orden estable. No se desplazan actividades existentes ni se duplican clases.

Dos confirmaciones explícitas explican que no hay deshacer. Un cambio del conjunto o un turno que alcanza su inicio exige nueva revisión y revierte la operación. El resultado conserva cantidades y listas consultables de creadas y omitidas. Sin candidatas se informan causas sin ofrecer confirmar una creación vacía.

### 8.3 Clase concreta y aviso de asistencia

La ficha presenta turno, sede, cancha, estado, origen manual o generado, profesores y participantes en filas. Administración consulta el registro completo; el profesor asignado para dictar consulta el grupo autorizado; el participante consulta su clase, profesores y datos propios sin una nómina personal ajena. Participar como profesor en calidad de alumno no concede permisos docentes.

Crear una clase puntual parte de un turno libre y utiliza Profesores → Participantes → Resumen dentro del panel de Agenda. Participantes permite continuar sin asignados y ofrece observaciones opcionales. Atrás conserva datos. Al confirmar se revalidan funcionamiento, inicio, ocupación y disponibilidad personal. Las altas de participantes comienzan en Asistirá; los docentes no tienen respuesta.

La edición administrativa permite observaciones y asignaciones en clases Programadas; cambiar cancha o anular exige inicio futuro. Cambiar cancha conserva día y hora. Cambiar día u horario requiere anular y crear otra clase independiente, sin vínculo de reprogramación de clases. Las Finalizadas conservan asignaciones y permiten asistencia al autorizado; las Anuladas conservan historia.

Cada fila de participante muestra Asistirá o No asistirá. El titular despliega No asisto o Asisto, según corresponda, antes del inicio de una clase Programada y con asignación activa. El formulario sólo se muestra bajo demanda; permite registrar o retirar el aviso sin límite y sin revalidar disponibilidad. El texto explica que el horario sigue ocupado y que la asistencia real se registra por separado. No se solicita confirmación de participación ni se muestra Sin respuesta.

No asistirá conserva la ocupación del horario y no retira asignación, responde otras clases ni modifica plantilla o asistencia. Profesores no responden por docencia; una imposibilidad se resuelve con reemplazo de asignación, conservando historial. Administración no responde por los participantes.

### 8.4 Asistencia compacta

Registrar asistencia, Corregir asistencia o Finalizar y registrar asistencia abre un único editor de clase. Se muestran personas con estado Presente, Ausente o Sin registrar y una acción Editar asistencia por fila. Sólo una fila despliega estado y observaciones; abrir otra conserva los cambios locales hasta el envío común.

Agregar persona revela una única búsqueda para quienes no estaban asignados. No exige Alumno ni contratación y no modifica la programación futura. No hay selectores permanentes por fila, autoguardado ni Marcar todos presentes.

Guardar asistencia confirma el conjunto sin paso de revisión adicional. La clase debe estar Finalizada; la operación conjunta sólo permite finalizar si terminó el turno. Un error identifica la fila y no guarda parcialmente. Si se pierde autorización o cambia el registro, se exige revisar.

La intención y la asistencia efectiva se presentan separadas: una persona puede estar Presente aunque haya avisado No asistirá. La carga no cambia el aviso de asistencia. La finalización automática no marca presentes o ausentes.

### 8.8 Ajustes administrativos de horas

El detalle de contratación prioriza lectura: dos resúmenes compactos, uno por rol, muestran cupo contratado, otorgadas, descontadas, comprometidas, consumidas y disponibles. El historial de ajustes usa filas con fecha, rol, operación, cantidad y motivo visible para el titular; una expansión permite consultar responsable y reversión. No se repiten formularios ni controles completos por fila.

Sólo administración ve Ajustar horas y sólo en contrataciones Activas del mes vigente o programadas para un período futuro. El disparador abre el formulario de rol, otorgar/quitar, cantidad entera positiva y motivo, indicando que lo verá el titular. La revisión presenta contratación, período, saldo y efecto antes de confirmar. Un descuento excedido indica el máximo sin modificar participaciones.

Cada ajuste elegible ofrece Revertir bajo demanda mediante una única acción de fila. Abre motivo y revisión del efecto inverso; no permite editar, borrar, revertir dos veces ni dejar saldo negativo. El estado vacío muestra un texto breve y, para el administrador autorizado, un solo disparador. El titular consulta el historial sin controles administrativos.


## 9. Catálogos, contrataciones y usos

### 9.1 Catálogos administrativos y oferta

Los catálogos de Planes y Membresías de socios usan lista e inspector, búsqueda por nombre/descripción y filtro de estado. La ficha muestra nombre, estado, configuración, precios vigentes y descripción; fechas en información secundaria. Agregar, Editar y Activar/Desactivar son acciones separadas y explícitas.

| Producto | Campos y reglas de presentación |
|---|---|
| Plan | Nombre, descripción, modalidad Individual/Grupal, uno a siete encuentros semanales, una o dos clases de una hora por encuentro y precio no negativo |
| Membresía de socio | Nombre, descripción, cupos mensuales positivos e independientes de organizador e invitado, precio mensual y adicional no negativo por invitado no socio |

El nombre es único entre Activos de su propio catálogo sin distinguir mayúsculas. La configuración estructural queda en lectura si hay cualquier contratación histórica: modalidad, frecuencia y duración del plan, o ambos cupos mensuales de la membresía. Para otro cupo se registra otro producto. Nombre, descripción y precios pueden actualizarse sin alterar importes aplicados. Desactivar impide nuevas contrataciones y no anula las existentes.

La membresía no presenta variantes por día ni límite diario. La oferta inicial de diez horas de organizador y diez de invitado, ARS 40.000 mensuales y ARS 12.500 por invitado no socio son datos configurables del producto, no constantes de interfaz.

Oferta utiliza pestañas Planes, Membresías y Tarifas y tarjetas comerciales para productos activos. Muestra nombre, precio y características; descripción hasta dos líneas y Leer descripción en modal si existe texto. La tarjeta no funciona como enlace completo a una ficha administrativa. Las tarifas muestran sedes activas con precio configurado y acceso a Agenda. Oferta enlaza al recorrido propio autorizado de §10 sin abrir un formulario en cada tarjeta. No registra cobros ni permite contratar un plan nuevo o distinto por el portal.

### 9.2 Registro y detalle de contratación

La lista administrativa filtra por tipo, titular, producto, mes y estado. La ficha prioriza producto, titular, mes cubierto, período, importe aplicado y estado; después situación financiera, usos por rol e historial de ajustes.

Registrar o renovar utiliza dos momentos: selección de usuario existente y producto Activo, y datos de contratación. Se muestran mes, período calculado, fecha efectiva, precio del producto en lectura y observaciones. Volver conserva selección y datos; cambiar producto propone su precio vigente. Sólo la confirmación registra. Renovar otro mes crea otra contratación, sin modificar la anterior.

El alta administrativa admite meses desde agosto de 2026 hasta el siguiente al actual; ese mes siguiente sólo se habilita desde el día 25 inclusive para altas, renovaciones y cambios. Este límite no impide operar el mes vigente, históricos permitidos o modificar horarios. La fecha efectiva está entre el inicio operativo y hoy y es independiente del mes cubierto. Una histórica terminada nace Vencida; una futura Activa sólo cubre su mes. Se admite un plan y una membresía simultáneos, pero una sola contratación no Anulada por titular, mes y tipo, incluidas las Vencidas.

Planes y membresías tienen precio mensual fijo: al confirmar se copia el vigente en precio_aplicado, sin edición del importe, descuentos o recargos por fecha de pago. Un cambio durante la revisión exige otra confirmación; un aumento posterior no altera el importe registrado. La membresía cubre el mes completo sin prorrateo y las altas tardías de planes se coordinan con administración.

Registrar un plan Activo puede otorgar Alumno al titular no administrativo; Profesor no contrata plan mientras conserve ese rol. Contratar membresía no otorga Alumno y se admite para profesores. No genera clases, asignaciones ni consumos.

Anular sólo se ofrece para Activas y abre revisión de página completa con motivo. Una membresía aplicada como organizador o invitado socio vigente Pendiente/Aceptado en reserva Programada impide anular y se explica el vínculo. Rechazadas, retiradas y reservas Anuladas o Finalizadas no bloquean. Se conserva historia, cobros y roles. El reemplazo del mismo titular y mes descuenta usos conservados, aunque cambie el producto o cupo.

### 9.3 Consulta propia y comprobante

Mis contrataciones muestra únicamente las propias, con tipo, producto, mes, importe y estado. Mantiene Activas, Anuladas y Vencidas, incluso de productos Inactivos. El detalle propio no muestra responsables, observaciones internas ni motivo libre de anulación. Ofrece Renovar el mismo plan cuando corresponde; Contratar membresía está en la consulta de contratos. Anular, reemplazar o cambiar un plan son operaciones administrativas.

El comprobante presenta contratación, producto, período y condiciones e importe guardados; acredita contratación, no pago. Administración consulta todos y el titular sólo los propios. Puede imprimir o guardar desde el navegador, también para Anuladas o Vencidas.

### 9.4 Uso de membresías

La consulta propia o administrativa selecciona mes o rango de hasta 366 días. Presenta por rol el cupo aplicado, horas otorgadas y descontadas, comprometidas, consumidas y disponibles derivadas, con detalle de reserva y contratación concreta. Los usos del mismo titular y mes de contrataciones Anuladas se conservan al calcular el cupo del reemplazo. Si alcanzan o superan el cupo nuevo no se muestran horas disponibles negativas: se informa que no quedan horas.

Las reservas Anuladas que computan por cancelación propia tardía se incluyen; las canceladas administrativamente no consumen. Las participaciones con beneficio de invitado se muestran en su cupo: comprometen desde Pendiente y consumen desde el inicio, aun sin respuesta. Las de reservas normales y las que tienen adicional no usan horas. No hay saldo editable, reinicio mensual manual ni arrastre al mes siguiente.

## 10. Contratación propia y seguimiento de planes

### 10.1 Operaciones del titular

Mis contrataciones ofrece Contratar membresía y Renovar el mismo plan bajo demanda. En membresías se selecciona producto Activo y mes actual o siguiente habilitado. La renovación conserva el producto de una contratación no Anulada propia y propone el mes siguiente al de referencia, sin permitir cambiar frecuencia, modalidad o duración. No requiere una aprobación individual de administración.

El mes siguiente al actual se ofrece desde el día 25 inclusive en Salta y antes de esa fecha no se confirma su contratación, tampoco desde administración. El portal no ofrece meses históricos. Las altas iniciales de planes y los cambios de producto, asignaciones o horarios son administrativos; renovar no modifica la programación por sí solo.

El formulario no solicita otro titular ni una fecha efectiva o precio editables. Usa la cuenta autenticada y fecha local del servidor. El recorrido tiene Selección, Revisión y Confirmación. La revisión muestra producto, características, mes, período e importe definitivo y aclara que no acredita un pago ni asigna horarios automáticamente. Atrás conserva selección; Cancelar abandona sin registrar.

Confirmar revalida permisos, cuenta, calendario, precio, producto, referencia de renovación y exclusividad por tipo/mes. Un cambio de condiciones exige revisar. Reenvíos no duplican contratos ni cobros; una contratación existente se consulta sin sobrescribirla ni presentar otro producto como el confirmado. El éxito muestra contrato, estado y comprobante.

Los beneficios rigen para el mes cubierto sin exigir cobro previo. Se utilizan los mismos estados Activo, Anulado y Vencido, sin una solicitud comercial, aprobación o estado de pago. El titular coordina anulaciones y reemplazos con administración. No hay renovación automática ni una encuesta de intención.

### 10.2 Seguimiento desde plantilla

Desde la plantilla semanal, administración solicita consultar contrataciones y elige un mes. El resultado presenta personas, horarios previstos y el plan no Anulado del período o Sin contratación. Se pueden localizar los casos sin contratación y comparar productos de meses contiguos para revisar la programación. Una fila ofrece consulta y acceso a la operación administrativa propia; no monta un formulario completo por persona.

Sin contratación no significa baja, indecisión, deuda ni falta de pago. Las participaciones de prueba y acuerdos fuera de un plan conservan sus recorridos. La consulta no retira ni reincorpora personas automáticamente y no ofrece eliminar en lote a quienes no contrataron.

El mes elegido identifica la consulta comercial, sin crear versiones mensuales de la plantilla. Modificar asignaciones conserva su recorrido, revisión y auditoría, sin alterar clases concretas, respuestas, asistencia ni cobros. Las respuestas propias de invitados y participantes siguen perteneciendo a sus actividades, no a una renovación.

## 11. Usuarios, perfiles y acceso

### 11.1 Usuarios y roles

La lista administrativa muestra persona/usuario, roles y estado, con búsqueda por nombre, apellido, celular, correo o usuario y filtros por rol y estado. La ficha conserva contacto, datos personales, roles, observaciones y fechas. Cuenta y actividad se agrupan en un bloque secundario; Actividad de clases y Actividad de reservas aparecen contiguas.

Acciones revela Modificar correo, Gestionar roles, Cambiar estado o Restablecer contraseña según permisos y elegibilidad. Los demás datos personales no tienen edición general. No se agregan checkboxes para operaciones masivas sobre usuarios.

Registrar usuario es independiente de reservar o contratar. Requiere nombre, apellido, correo único, móvil argentino, nacimiento y contraseña ingresada o sugerida; el usuario generado se presenta en lectura, con Profesor o Alumno opcional en alta administrativa. Las credenciales definitivas se muestran una sola vez, no como dato de perfil. No se exponen hashes.

Público es permanente. Administrador es exclusivo y se crea por operación técnica, sin CRUD de roles. Profesor y Alumno son incompatibles. Retirar roles explica las relaciones que lo impiden: planes Activos para Alumno, reservas Programadas para Reservas y docencia Programada para Profesor. Una membresía no impide retirar Alumno ni crea un rol Socio. Ninguna cuenta con permiso de cambio de estado puede desactivarse a sí misma. Desactivar un administrador exige que quede otro activo; estas condiciones se revalidan al confirmar.

### 11.2 Perfil propio y credenciales

El perfil propio es de lectura para cualquier titular autenticado. La única edición es Cambiar mi contraseña. Para el correo se indica que debe gestionarlo con administración. Los controles administrativos sólo se muestran a administración; consultar una ficha o tener Profesor o Alumno no concede esas acciones.

Ingreso pide usuario y contraseña. Registro, recuperación y cambio se abren como tareas explícitas en el panel de acceso. Las contraseñas permiten mostrar/ocultar y pegar. Recuperación responde de forma genérica, sin revelar existencia de cuenta; el enlace tiene vigencia de una hora y su estado vencido permite solicitar otro.

Una contraseña provisoria exige reemplazo antes de acceder al sistema. Ese recorrido no ofrece Cancelar o Postergar; permite completar cambio, recuperar acceso o cerrar sesión. Cerrar sesión utiliza una operación explícita protegida, sin asumir que cerrar la pestaña invalida la cuenta.

### 11.3 Actividad propia y administrativa

Mi actividad → Clases presenta Próximas, Historial y Anuladas. Cada entrada muestra fecha, hora, sede, cancha, estado y función propia; seleccionarla abre inspector y permite Ver clase o Ver en agenda. La participación no atribuye cada clase a una contratación ni habilita autoinscripción, edición de asistencia o solicitud de recuperación.

Mi actividad → Reservas admite rango de hasta 366 días y estado Programada/Finalizada/Anulada. Las columnas son número, fecha/hora, sede/cancha, estado, relación e importe aplicado. Relación dice Organiza o Invitado; para Invitado el importe es «—» y no existe valor financiero oculto en la respuesta. El inspector aplica §7.6 y permite la respuesta propia cuando corresponda. La creación permanece en Agenda.

Sin Reservas se muestra «Para consultar tus reservas necesitás el rol Reservas», sin registros ni excepción por invitación; Clases permanece accesible. La relación histórica se conserva. La actividad administrativa desde Usuarios mantiene ambas relaciones, importes y permisos administrativos, incluso si la persona pierde ese rol; no es una suplantación de la lectura del portal.

## 12. Instalaciones y feriados

La lista de sedes permite búsqueda por nombre y estado. La ficha de sede usa navegación local Datos, Canchas, Horarios y Tarifa. Las canchas son filas con nombre, superficie y estado, sin formularios montados por fila. Registrar y editar sede o cancha no mezcla el cambio de estado con la edición de datos.

Los horarios muestran los siete días, con hasta dos franjas por día. Configurar revela selección de uno o varios días y accesos para lunes a viernes, fin de semana o semana completa. Inicio y fin son en punto; dos franjas exigen una hora sin funcionamiento entre ellas. Sin franjas significa sin funcionamiento, no un formulario vacío que sugiera horario por defecto. Se rechaza un cambio que deje fuera una actividad Programada cuyo turno aún no terminó.

La tarifa es un precio positivo por hora y sede, común a sus canchas. Si no existe se muestra Sin tarifa configurada con acción administrativa para establecerla; no se puede confirmar normal y sí puede aplicarse membresía si cumple sus reglas. Guardar el mismo valor no inventa un error de negocio.

Desactivar abre revisión de eventos futuros y se impide si hay una actividad en curso. Confirmar anula todos los eventos revisados y desactiva juntos; las reservas liberan horas de membresía y conservan cobros e historia. Reactivar no restaura eventos ni cambia automáticamente el estado individual de canchas.

Feriados usa lista fecha/descripción y ficha de lectura. Registrar uno futuro presenta las clases Programadas afectadas de todas las sedes y confirma registro y anulaciones juntos, sin modificar reservas ni crear bloqueos. Registrar hoy o pasado no modifica clases existentes. Quitar no reactiva ni genera clases. Una clase manual en feriado es una operación explícita que respeta las demás reglas.

## 13. Caja y cobros

### 13.1 Sesión y movimientos

Caja presenta primero sesión, estado, responsable fijo y efectivo esperado; después resumen por clase y medio, con devoluciones separadas, y movimientos. No usa gráficos, indicadores de deuda ni saldos bancarios.

Sin sesión abierta, Abrir caja revela efectivo inicial no negativo, referencia al último contado y motivo si difiere. Sólo puede existir una sesión abierta. Su responsable puede registrar y cerrar; los demás administradores sólo consultan. No se reasigna ni reabre una sesión.

Registrar movimiento revela campos según la clase:

| Clase | Campos y comportamiento |
|---|---|
| Ingreso | Categoría determinada por el origen (Reservas, Planes, Membresías u Otros), concepto, monto positivo, medio y vínculo opcional con una contratación concreta de plan, membresía o reserva; como máximo un origen |
| Egreso | Categoría, concepto, monto y medio; destinatario de texto opcional bajo demanda; no crea cuentas para proveedores |
| Devolución | Egreso con vínculo opcional a reserva o contratación concreta; contexto compacto y máximo disponible, sin modificar ingresos originales |
| Aporte/Retiro | Concepto y monto, exclusivamente efectivo; no se cuentan como ingreso/gasto operativo |

Los medios son Efectivo, Transferencia, Tarjeta y QR. Los no efectivos exigen referencia y verificación manual. Egresos y retiros en efectivo no pueden superar el disponible. La fecha la asigna el servidor, sin carga retroactiva o futura.

Al vincular un ingreso, la categoría se determina por el tipo de origen y se muestra sin selector editable. Sin vínculo, la categoría es Otros y no se muestra un selector. Reservas, Planes y Membresías requieren el vínculo correspondiente. La categoría agrupa los cobros y el vínculo conserva el registro concreto pagado.

Registrar ingreso presenta origen, selección del registro y datos del cobro; el ingreso sin vínculo pasa directamente del origen a los datos. Las categorías de origen se eligen mediante tarjetas con un check y se avanza con «Siguiente». Las reservas y contrataciones se buscan por persona, usuario y datos del registro, con resultados compactos y paginados. Las tarjetas oscuras muestran caja y tipo de origen. Los datos del registro vinculado se consultan desde el tooltip «?» de Origen: para reservas muestra organizador, importe aplicado, sede, cancha, turno, modalidad y categoría; para contrataciones muestra producto, titular, importe aplicado, mes cubierto, fecha de alta y categoría. «Volver» conserva los campos del cobro al elegir otro registro o categoría de origen. Los cobros vigentes del origen se consultan bajo demanda. La referencia y verificación del pago aparecen únicamente para medios no efectivos. Los errores se presentan junto al campo o como alerta del formulario.

El ingreso puede ser parcial y pueden existir varios por origen, mostrando la comparación entre importe acordado y neto recibido sin modificar el precio aplicado. No admite nuevos cobros vinculados a contrataciones o reservas Anuladas. El reenvío se identifica por UUID de operación; no duplica movimientos ni acepta contenido distinto para el mismo identificador.

Para Devoluciones, Vincular operación revela el selector de reserva o contratación; no aparece un formulario de vínculo abierto por defecto. La búsqueda es compacta y paginada, con contexto del origen, ingresos Vigentes, devoluciones Vigentes y máximo disponible. Se admite origen Anulado con cobros. La revisión muestra monto, medio, concepto y efecto sobre el neto; confirmar revalida el máximo bajo bloqueo. Sin vínculo se exige concepto y validaciones habituales. Otros egresos no ofrecen vínculo comercial.


### 13.2 Anulación y cierre

Anular un movimiento Vigente exige motivo y revisión de página completa. Si anular un ingreso revela neto comercial negativo, la revisión muestra la diferencia y conserva las devoluciones. Se permite corregir el ingreso manteniendo las validaciones de caja; no se generan movimientos compensatorios ni nuevas devoluciones con neto no positivo. Lo opera el responsable de la sesión abierta actual, incluso si pertenece a otra sesión cerrada. La vista distingue sesión actual y origen, el efecto sobre efectivo y los cierres históricos preservados. Una anulación no es devolución y la corrección se carga como operación independiente.

Cerrar caja presenta esperado, contado no negativo, diferencia y motivo obligatorio cuando difieren. Se revalida el cálculo definitivo al confirmar. El cierre guarda sus resultados y no ofrece editar, reabrir o reasignar. Anulaciones posteriores se identifican en la consulta sin reescribir el cierre guardado. No se confirman operaciones que dejen efectivo esperado negativo en una sesión abierta.

### 13.3 Historial y cobros comerciales

El historial filtra sesiones por apertura y estado y movimientos por momento de registro, sesión, clase, categoría, medio y estado. Los ingresos se resumen por categoría. El detalle muestra concepto, monto, medio, referencia, categoría/destinatario, origen, responsable, fecha y anulación. Se distingue la consulta de movimientos Vigentes de la reconstrucción al cierre, incluidas anulaciones posteriores y sesiones que atraviesan medianoche.

Desde contrataciones y reservas se muestran importe acordado, ingresos Vigentes, devoluciones Vigentes y neto recibido. El historial de movimientos, incluidos los Anulados, se despliega bajo demanda y se pagina de a 25 registros. Cada fila muestra tipo, fecha, monto y estado, con un único disparador para consultar concepto, medio, referencia y motivo de anulación. El administrador puede abrir el movimiento en caja; el titular consulta sus detalles dentro de la propia operación. Los movimientos permanecen en su origen y no se ofrece selección de destino ni compensación entre operaciones. Al registrar un cobro de contratación se muestran producto, mes, precio_aplicado y cobros anteriores, sin sustituir el precio por el del catálogo actualizado. El concepto permite explicar un parcial o acuerdo excepcional sobre el dinero recibido sin alterar el precio confirmado; las observaciones de contratación conservan acuerdos generales. Se presenta Falta cobrar, Cubierto o Excedente por resolver según el neto y el importe acordado, sin devolución automática. En operaciones Anuladas sólo se muestran movimientos y neto, sin exigir completar el precio ni presumir reintegro. Un neto negativo destaca una diferencia para revisión administrativa. Registrar cobro se revela sólo al administrador que puede operar su sesión y cuando el origen lo permite. El titular consulta sus cobros sin acceso a caja o movimientos ajenos; el invitado no accede a cobros de la reserva.

Un fallo de caja no revierte una reserva o contratación confirmada. Una nueva reserva conserva sus propios movimientos y Actualizar socios no modifica cobros existentes.

## 14. Auditoría y comunicación

Auditoría es administrativa y de sólo lectura. Cambios e Intentos rechazados son consultas diferenciadas, paginadas y con una expansión de lectura por fila. No ofrece edición, borrado, registro manual ni acciones para ejecutar tareas.

Cambios muestra momento, tabla, registro, acción y responsable/origen. La expansión conserva valores anteriores/actuales, actor de aplicación cuando existe, usuario PostgreSQL, origen y UUID. No muestra contraseñas, hashes ni secretos. Las altas y consultas no se presentan como modificaciones auditadas.

Intentos rechazados identifica tipo, motivo de catálogo, destino, método y UUID; los accesos ocultos por privacidad no revelan el registro ajeno al usuario rechazado. Las consultas de administración no transforman el historial en una herramienta de edición.

La comunicación automática utiliza email, sin bandeja interna, campana ni preferencias nuevas. Los mensajes identifican actividad o mes y enlazan una ruta que vuelve a exigir autenticación y autorización. Una notificación de invitación no acredita aceptación; una de asignación no acredita asistencia. Se conservan los casos de alta, recuperación, confirmación de reserva, invitación, cancelación, asignación, vencimiento y recordatorios. La contratación propia no exige responder encuestas ni genera recordatorios de encuesta o de renovación comercial.

No se añaden botones para ejecutar vencimiento o finalización automática ni marcas que simulen envíos de email realizados. La finalización horaria sólo cierra eventos; el vencimiento comercial no retira roles ni genera cobros.

## 15. Accesibilidad y comportamiento técnico

Cada pantalla tiene un h1 y secciones jerárquicas. Tablas usan caption y encabezados; etiquetas y ayudas tienen asociación programática. Las acciones de fila incluyen contexto accesible, por ejemplo «Editar asistencia de Ana Pérez». Se ofrece Saltar al contenido y la ruta activa se indica mediante `aria-current`.

Tab y Mayús+Tab recorren controles en orden de lectura; Enter activa enlaces y Enter/Espacio los revelados. No se usan valores positivos de tabindex, hover obligatorio ni color como único medio. Menús y pestañas tienen el patrón de teclado y semántica correspondiente a su comportamiento real; no se declaran roles de combobox sin implementar su interacción completa.

El inspector recibe foco en el título cuando se abre y Cerrar lo devuelve a la fila; cambiar filtros conserva el foco del control. Agenda mantiene la selección y actualización de panel sin saltos al mover el foco. Las confirmaciones difíciles de revertir enfocan título o alternativa segura. Los campos ocultos o sin permiso no permanecen montados ni se incluyen como datos recuperables en la respuesta.

Carga y resultados usan anuncios de estado; errores de envío usan alerta o resumen enfocado. Se respeta reducción de movimiento y no se usa animación para ocultar falta de respuesta. El tamaño útil de un control compacto incluye área activable y separación, no sólo el dibujo de su icono.

Con zoom de 200% y 400%, navegación, formularios y fichas redistribuyen contenido sin controles cortados ni foco tapado. La excepción bidimensional se limita a grillas y tablas que la requieren, no a toda la página. El cumplimiento de contraste de los pares no constituye por sí solo una certificación global de accesibilidad.

Las escrituras conservan CSRF, validación de formularios, permisos, control de versiones y transacciones. El cliente no decide cobertura, consumo, disponibilidad o autorización. No se anuncia éxito antes de confirmar ni se guardan partes de una operación conjunta.

Las actualizaciones parciales tienen un único responsable del fragmento. Los inicializadores son idempotentes y al reemplazar contenido se limpian listeners, solicitudes y diálogos. Login, 403, 404 y errores no se insertan como si fueran resultados válidos. Las respuestas atrasadas se descartan. URL, filtros y selección permiten recarga, enlaces directos y retorno coherente sin almacenar secretos en historial o almacenamiento local.

Se reutilizan componentes sólo donde comparten un contrato concreto: navegación, migas, lista/inspector, estados, campos, búsqueda de personas, confirmación y mensajes. Los recursos se cargan por página. No se incorporan bibliotecas ni tecnologías por sugerencias de una evaluación técnica sin una necesidad funcional concreta.

## 16. Límites de interfaz y revisión manual

No se ofrecen reservas recurrentes, reservas agrupadas de varias horas, arrastre de eventos, autoinscripción a clases, contratación de planes nuevos o distintos desde el portal, cobro online, solicitudes de recuperación de clases, contabilidad general, salarios, edición general de datos personales, CRUD de roles, reapertura de caja o deshacer generación. Los formularios de recuperación de contraseña sí forman parte del acceso.

La revisión manual de cada entrega comprueba:

- Lectura inicial compacta, acciones bajo demanda y comportamiento con una, diez y cincuenta filas.
- Permisos de administración, titular, invitado, participante y docente, también por URL directa y respuestas del servidor.
- Claro y oscuro completos, estados, foco, rayado y composición de turnos iniciados.
- Teclado, cierre y retorno de foco, errores por campo, zoom y conservación del contexto.
- Vacío, carga, error, reintento y descarte de respuestas atrasadas.
- Precios o condiciones modificados durante la revisión, reenvíos y operaciones simultáneas sin efectos parciales.
- Cupos, cambio de mes, tres días de reserva, umbral exacto de dos horas, inicio de actividades y apertura de contratación del mes siguiente desde el día 25.
- Separación entre importe aplicado y cobros, respuesta y asistencia, estado de evento y resultado de uso, plantilla y clases concretas.

Las revisiones se realizan sobre la funcionalidad entregada y no crean ni ejecutan pruebas automatizadas. El trabajo se cierra por grupo funcional para revisión del usuario; el asistente no hace commits.
