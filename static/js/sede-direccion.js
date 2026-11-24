document.addEventListener("DOMContentLoaded", function () {
    function prepararBloque(bloque) {
        if (bloque.dataset.sedeDireccionPreparada) return;
        bloque.dataset.sedeDireccionPreparada = "true";

        var buscarUrl = bloque.dataset.buscarUrl || "";
        var esEdicion = bloque.dataset.esEdicion === "1";
        var sedeEstructurada = bloque.dataset.sedeEstructurada === "1";
        var sedeOrigenGeoref = bloque.dataset.sedeOrigenGeoref === "1";
        var provincia = bloque.dataset.provincia || "Salta";

        var inputTokenFormulario = bloque.querySelector("[data-dir-token-formulario]");
        var inputModo = bloque.querySelector("[data-dir-modo]");
        var inputTokenSeleccion = bloque.querySelector("[data-dir-token-seleccion]");
        var selectLocalidad = bloque.querySelector("[name='localidad_codigo']");
        var inputConsulta = bloque.querySelector("[name='direccion_consulta']");
        var inputCalle = bloque.querySelector("[name='calle']");
        var inputAltura = bloque.querySelector("[name='altura']");
        var inputCpa = bloque.querySelector("[name='cpa']");
        var checkConfirmacion = bloque.querySelector("[name='confirmacion_direccion_manual']");

        var resumenTexto = bloque.querySelector("[data-dir-resumen-texto]");
        var resumenOrigen = bloque.querySelector("[data-dir-resumen-origen]");
        var botonAbrir = bloque.querySelector("[data-dir-abrir]");
        var panel = bloque.querySelector("[data-dir-panel]");
        var errorPanel = bloque.querySelector("[data-dir-error-panel]");

        var bloqueGeoref = bloque.querySelector("[data-dir-bloque-georef]");
        var bloqueManualCabecera = bloque.querySelector("[data-dir-bloque-manual-cabecera]");
        var campoCalle = bloque.querySelector("[data-dir-campo-calle]");
        var camposDetalle = bloque.querySelector("[data-dir-campos-detalle]");
        var bloqueConfirmacion = bloque.querySelector("[data-dir-confirmacion-manual]");

        var botonBuscar = bloque.querySelector("[data-dir-buscar]");
        var cajaEstado = bloque.querySelector("[data-dir-estado]");
        var listaResultados = bloque.querySelector("[data-dir-resultados]");
        var seleccionResumen = bloque.querySelector("[data-dir-seleccion-resumen]");
        var seleccionCalle = bloque.querySelector("[data-dir-seleccion-calle]");

        var botonIrManual = bloque.querySelector("[data-dir-ir-manual]");
        var botonIrGeoref = bloque.querySelector("[data-dir-ir-georef]");
        var botonCancelar = bloque.querySelector("[data-dir-cancelar]");
        var botonAplicar = bloque.querySelector("[data-dir-aplicar]");

        var instantanea = null;
        var solicitudActiva = 0;

        function guardarReferenciaGeoref(ubicacion, localidad) {
            if (ubicacion && typeof ubicacion.lat === "number" && typeof ubicacion.lon === "number" && localidad) {
                bloque.dataset.georefLat = String(ubicacion.lat);
                bloque.dataset.georefLon = String(ubicacion.lon);
                bloque.dataset.georefLocalidad = localidad;
            } else {
                delete bloque.dataset.georefLat;
                delete bloque.dataset.georefLon;
                delete bloque.dataset.georefLocalidad;
            }
        }

        function notificarCambioDireccion() {
            bloque.dispatchEvent(new CustomEvent("sede-direccion:cambio", {
                bubbles: true,
                detail: { localidad: (selectLocalidad && selectLocalidad.value) || "" },
            }));
        }

        function textoLocalidadSeleccionada() {
            if (!selectLocalidad || !selectLocalidad.value) return "";
            var opcion = selectLocalidad.options[selectLocalidad.selectedIndex];
            return opcion ? opcion.text.trim() : "";
        }

        function componerTextoDireccion(calle, altura, localidadTexto, cpa) {
            var calleLimpia = (calle || "").trim().replace(/\s+/g, " ");
            var alturaLimpia = (altura || "").trim().replace(/\s+/g, " ");
            if (!calleLimpia || !alturaLimpia || !localidadTexto) return "";
            var base = calleLimpia + " " + alturaLimpia + ", " + localidadTexto + ", " + provincia;
            var cpaLimpio = (cpa || "").replace(/\s+/g, "").toUpperCase();
            return cpaLimpio ? base + " (" + cpaLimpio + ")" : base;
        }

        function mostrarErrorPanel(mensaje) {
            if (!errorPanel) return;
            if (!mensaje) {
                errorPanel.textContent = "";
                errorPanel.hidden = true;
                return;
            }
            errorPanel.textContent = mensaje;
            errorPanel.hidden = false;
        }

        function mostrarEstado(mensaje, tipo) {
            if (!cajaEstado) return;
            cajaEstado.className = "sede-direccion-estado";
            if (!mensaje) {
                cajaEstado.textContent = "";
                cajaEstado.hidden = true;
                return;
            }
            if (tipo) {
                cajaEstado.classList.add("sede-direccion-estado-" + tipo);
            }
            cajaEstado.textContent = mensaje;
            cajaEstado.hidden = false;
        }

        function limpiarResultados() {
            if (listaResultados) {
                listaResultados.innerHTML = "";
                listaResultados.hidden = true;
            }
            mostrarEstado("");
        }

        function limpiarErroresServidorPanel() {
            panel.querySelectorAll(".error-campo").forEach(function (el) {
                el.remove();
            });
            panel.querySelectorAll("[aria-invalid='true']").forEach(function (el) {
                el.removeAttribute("aria-invalid");
                el.removeAttribute("aria-describedby");
            });
        }

        function actualizarVistaModo() {
            var modo = (inputModo.value || "").trim();
            var esManual = modo === "manual";
            var tieneCalleSeleccionada = Boolean((inputCalle.value || "").trim()) && (
                (modo === "georef" && Boolean((inputTokenSeleccion.value || "").trim()))
                || modo === "editar_existente"
            );

            bloqueGeoref.hidden = esManual;
            bloqueManualCabecera.hidden = !esManual;
            campoCalle.hidden = !esManual;
            bloqueConfirmacion.hidden = !esManual;

            seleccionResumen.hidden = esManual || !tieneCalleSeleccionada;
            if (tieneCalleSeleccionada) {
                seleccionCalle.textContent = (inputCalle.value || "").trim();
            }

            var tieneErroresDetalle = Boolean(
                camposDetalle.querySelector(".error-campo")
            );
            camposDetalle.hidden = !esManual && !tieneCalleSeleccionada && !tieneErroresDetalle;
        }

        function guardarInstantanea() {
            instantanea = {
                modo: inputModo.value,
                tokenSeleccion: inputTokenSeleccion.value,
                localidad: selectLocalidad.value,
                consulta: inputConsulta.value,
                calle: inputCalle.value,
                altura: inputAltura.value,
                cpa: inputCpa.value,
                confirmacion: checkConfirmacion.checked,
                resumenTexto: resumenTexto.textContent,
                resumenVacio: resumenTexto.classList.contains("texto-secundario"),
                resumenOrigen: resumenOrigen.textContent,
                resumenOrigenOculto: resumenOrigen.hidden,
                botonTexto: botonAbrir.textContent,
            };
        }

        function restaurarInstantanea() {
            if (!instantanea) return;
            inputModo.value = instantanea.modo;
            inputTokenSeleccion.value = instantanea.tokenSeleccion;
            selectLocalidad.value = instantanea.localidad;
            inputConsulta.value = instantanea.consulta;
            inputCalle.value = instantanea.calle;
            inputAltura.value = instantanea.altura;
            inputCpa.value = instantanea.cpa;
            checkConfirmacion.checked = instantanea.confirmacion;
            resumenTexto.textContent = instantanea.resumenTexto;
            resumenTexto.classList.toggle("texto-secundario", instantanea.resumenVacio);
            resumenOrigen.textContent = instantanea.resumenOrigen;
            resumenOrigen.hidden = instantanea.resumenOrigenOculto;
            botonAbrir.textContent = instantanea.botonTexto;
            instantanea = null;
        }

        function abrirPanel() {
            guardarInstantanea();
            mostrarErrorPanel("");
            limpiarResultados();

            if (inputModo.value === "mantener") {
                if (esEdicion && sedeEstructurada) {
                    inputModo.value = sedeOrigenGeoref ? "editar_existente" : "manual";
                } else {
                    inputModo.value = "georef";
                }
            } else if (!inputModo.value) {
                inputModo.value = "georef";
            }

            actualizarVistaModo();
            panel.hidden = false;
            botonAbrir.hidden = true;
            botonAbrir.setAttribute("aria-expanded", "true");
            if (resumenTexto.classList.contains("texto-secundario")) {
                resumenTexto.hidden = true;
            }
            if (selectLocalidad && !selectLocalidad.value) {
                selectLocalidad.focus();
            } else if (inputModo.value === "manual") {
                inputCalle.focus();
            } else {
                inputConsulta.focus();
            }
        }

        function cerrarPanel(devolverFoco) {
            panel.hidden = true;
            botonAbrir.hidden = false;
            botonAbrir.setAttribute("aria-expanded", "false");
            resumenTexto.hidden = false;
            mostrarErrorPanel("");
            limpiarResultados();
            if (devolverFoco && botonAbrir) {
                botonAbrir.focus();
            }
        }

        function invalidarBusquedaAnterior() {
            solicitudActiva += 1;
            limpiarResultados();
            mostrarErrorPanel("");
            guardarReferenciaGeoref(null, "");
            if (inputModo.value !== "manual") {
                inputTokenSeleccion.value = "";
                inputCalle.value = "";
                inputModo.value = "georef";
                actualizarVistaModo();
            }
            notificarCambioDireccion();
        }

        function renderizarResultados(resultados) {
            listaResultados.innerHTML = "";
            if (!resultados.length) {
                listaResultados.hidden = true;
                mostrarEstado(
                    "No se encontraron coincidencias en Georef para esa localidad. Podés refinar la búsqueda o ingresar la dirección manualmente.",
                    "advertencia"
                );
                return;
            }

            mostrarEstado(
                resultados.length === 1
                    ? "Se encontró 1 coincidencia en Georef. Elegila para confirmar la calle."
                    : "Se encontraron " + resultados.length + " coincidencias en Georef. Elegí una para confirmar la calle.",
                "exito"
            );

            resultados.forEach(function (item) {
                var li = document.createElement("li");
                var boton = document.createElement("button");
                boton.type = "button";
                boton.className = "sede-direccion-resultado-boton";

                var titulo = document.createElement("strong");
                titulo.textContent = item.altura ? item.calle + " " + item.altura : item.calle;

                var detalle = document.createElement("span");
                var partes = [item.localidad_etiqueta + ", " + item.provincia];
                if (!item.altura) {
                    partes.push("confirmá la altura");
                }
                if (!item.tiene_ubicacion) {
                    partes.push("sin coordenadas en Georef");
                }
                detalle.textContent = partes.join(" · ");

                boton.appendChild(titulo);
                boton.appendChild(detalle);

                boton.addEventListener("click", function () {
                    limpiarErroresServidorPanel();
                    mostrarErrorPanel("");
                    inputModo.value = "georef";
                    inputTokenSeleccion.value = item.token;
                    inputCalle.value = item.calle;
                    if (item.altura) {
                        inputAltura.value = item.altura;
                    }
                    checkConfirmacion.checked = false;
                    guardarReferenciaGeoref(item.ubicacion_aproximada, item.localidad_codigo);
                    notificarCambioDireccion();

                    listaResultados.querySelectorAll(".sede-direccion-resultado-boton").forEach(function (b) {
                        b.classList.remove("seleccionado");
                        b.setAttribute("aria-pressed", "false");
                    });
                    boton.classList.add("seleccionado");
                    boton.setAttribute("aria-pressed", "true");

                    actualizarVistaModo();
                    inputAltura.focus();
                });

                li.appendChild(boton);
                listaResultados.appendChild(li);
            });
            listaResultados.hidden = false;
        }

        async function ejecutarBusqueda() {
            mostrarErrorPanel("");
            limpiarErroresServidorPanel();

            var localidad = (selectLocalidad.value || "").trim();
            var consulta = (inputConsulta.value || "").trim();

            if (!localidad) {
                mostrarErrorPanel("Elegí primero una localidad de Salta.");
                selectLocalidad.focus();
                return;
            }
            if (consulta.length < 2) {
                mostrarErrorPanel("Ingresá al menos 2 caracteres para buscar la calle en Georef.");
                inputConsulta.focus();
                return;
            }

            var idSolicitud = ++solicitudActiva;
            listaResultados.innerHTML = "";
            listaResultados.hidden = true;
            mostrarEstado("Buscando coincidencias en Georef...", "info");
            botonBuscar.disabled = true;

            try {
                var parametros = new URLSearchParams({
                    localidad: localidad,
                    consulta: consulta,
                    formulario: inputTokenFormulario ? inputTokenFormulario.value : "",
                });
                var respuesta = await fetch(buscarUrl + "?" + parametros.toString(), {
                    method: "GET",
                    cache: "no-store",
                    credentials: "same-origin",
                    headers: { "Accept": "application/json" },
                });
                if (idSolicitud !== solicitudActiva) return;

                var datos = null;
                try {
                    datos = await respuesta.json();
                } catch (errorJson) {
                    datos = null;
                }

                if (!respuesta.ok || !datos || !datos.ok) {
                    var mensaje = (datos && datos.error) || "No se pudo consultar Georef en este momento. Podés reintentar o ingresar la dirección manualmente.";
                    mostrarEstado(mensaje, "error");
                    return;
                }

                renderizarResultados(datos.resultados || []);
            } catch (error) {
                if (idSolicitud !== solicitudActiva) return;
                mostrarEstado(
                    "No se pudo conectar con Georef. Podés reintentar o ingresar la dirección manualmente.",
                    "error"
                );
            } finally {
                if (idSolicitud === solicitudActiva) {
                    botonBuscar.disabled = false;
                }
            }
        }

        botonAbrir.addEventListener("click", function () {
            if (panel.hidden) {
                abrirPanel();
            } else {
                restaurarInstantanea();
                cerrarPanel(true);
            }
        });

        botonBuscar.addEventListener("click", ejecutarBusqueda);

        inputConsulta.addEventListener("keydown", function (evento) {
            if (evento.key === "Enter") {
                evento.preventDefault();
                ejecutarBusqueda();
            }
        });

        inputConsulta.addEventListener("input", function () {
            invalidarBusquedaAnterior();
        });

        selectLocalidad.addEventListener("change", function () {
            invalidarBusquedaAnterior();
        });

        botonIrManual.addEventListener("click", function () {
            mostrarErrorPanel("");
            limpiarResultados();
            limpiarErroresServidorPanel();
            inputModo.value = "manual";
            inputTokenSeleccion.value = "";
            guardarReferenciaGeoref(null, "");
            actualizarVistaModo();
            notificarCambioDireccion();
            inputCalle.focus();
        });

        botonIrGeoref.addEventListener("click", function () {
            mostrarErrorPanel("");
            limpiarResultados();
            limpiarErroresServidorPanel();
            inputModo.value = "georef";
            inputTokenSeleccion.value = "";
            inputCalle.value = "";
            checkConfirmacion.checked = false;
            actualizarVistaModo();
            inputConsulta.focus();
        });

        botonCancelar.addEventListener("click", function () {
            solicitudActiva += 1;
            restaurarInstantanea();
            cerrarPanel(true);
        });

        botonAplicar.addEventListener("click", function () {
            mostrarErrorPanel("");
            var modo = (inputModo.value || "").trim();
            var localidad = (selectLocalidad.value || "").trim();
            var localidadTexto = textoLocalidadSeleccionada();
            var calle = (inputCalle.value || "").trim();
            var altura = (inputAltura.value || "").trim();
            var cpa = (inputCpa.value || "").replace(/\s+/g, "").toUpperCase();
            inputCpa.value = cpa;

            if (!localidad) {
                mostrarErrorPanel("Seleccioná una localidad habilitada de Salta.");
                selectLocalidad.focus();
                return;
            }

            if (modo === "georef") {
                if (!inputTokenSeleccion.value || !calle) {
                    mostrarErrorPanel("Buscá y seleccioná una coincidencia de Georef, o usá la carga manual.");
                    inputConsulta.focus();
                    return;
                }
            } else if (modo === "manual") {
                if (!calle) {
                    mostrarErrorPanel("Ingresá el nombre de la calle o ruta.");
                    inputCalle.focus();
                    return;
                }
            } else if (modo === "editar_existente") {
                if (!calle) {
                    mostrarErrorPanel("Buscá y seleccioná una calle en Georef o usá la carga manual.");
                    inputConsulta.focus();
                    return;
                }
            } else {
                mostrarErrorPanel("Buscá una calle en Georef o elegí la carga manual.");
                return;
            }

            if (!altura) {
                mostrarErrorPanel("Confirmá la altura de la sede (por ejemplo, 643, 643 B, Km 12 o s/n).");
                inputAltura.focus();
                return;
            }

            if (modo === "manual" && !checkConfirmacion.checked) {
                mostrarErrorPanel("Confirmá que verificaste la calle y altura con la sede o una fuente oficial.");
                checkConfirmacion.focus();
                return;
            }

            resumenTexto.textContent = componerTextoDireccion(calle, altura, localidadTexto, cpa);
            resumenTexto.classList.remove("texto-secundario");
            resumenOrigen.textContent = modo === "manual"
                ? "Carga manual confirmada"
                : "Normalizada con Georef";
            resumenOrigen.hidden = false;
            botonAbrir.textContent = "Cambiar dirección";
            instantanea = null;
            notificarCambioDireccion();
            cerrarPanel(true);
        });

        inputCpa.addEventListener("input", function () {
            var pos = inputCpa.selectionStart;
            inputCpa.value = inputCpa.value.toUpperCase();
            if (typeof pos === "number") {
                inputCpa.setSelectionRange(pos, pos);
            }
        });

        actualizarVistaModo();
    }

    function prepararEn(raiz) {
        raiz.querySelectorAll("[data-sede-direccion]").forEach(prepararBloque);
    }

    prepararEn(document);
    document.addEventListener("modal-formulario:cargado", function (evento) {
        prepararEn(evento.target);
    });
});
