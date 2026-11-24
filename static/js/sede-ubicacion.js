document.addEventListener("DOMContentLoaded", function () {
    var instanciasActivas = new WeakMap();

    function destruirMapaEn(contenedor) {
        var mapa = instanciasActivas.get(contenedor);
        if (mapa) {
            try {
                mapa.remove();
            } catch (error) {
                // La instancia ya fue liberada o desmontada del DOM.
            }
            instanciasActivas.delete(contenedor);
        }
    }

    function crearIconoPin(bloque) {
        if (typeof window.L === "undefined") return undefined;
        return window.L.icon({
            iconUrl: bloque.dataset.markerIcon,
            iconRetinaUrl: bloque.dataset.markerIcon2x,
            shadowUrl: bloque.dataset.markerShadow,
            iconSize: [25, 41],
            iconAnchor: [12, 41],
            popupAnchor: [1, -34],
            shadowSize: [41, 41],
        });
    }

    function parsearCoordenada(texto) {
        var limpio = (texto || "").trim().replace(",", ".");
        if (!limpio) return null;
        var num = Number(limpio);
        return Number.isFinite(num) ? num : null;
    }

    function formatearCoordenada(num) {
        return Number(num).toFixed(6);
    }

    function prepararBloque(bloque) {
        if (bloque.dataset.sedeUbicacionPreparada) return;
        bloque.dataset.sedeUbicacionPreparada = "true";

        var formulario = bloque.closest("form");
        var dialogo = bloque.closest("dialog");
        var centros = {};
        try {
            centros = JSON.parse(bloque.dataset.centros || "{}");
        } catch (error) {
            centros = {};
        }
        var teselasUrl = bloque.dataset.teselasUrl || "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
        var atribucion = bloque.dataset.atribucion || "© OpenStreetMap";
        var zoomMax = parseInt(bloque.dataset.zoomMax || "19", 10) || 19;

        var inputModo = bloque.querySelector("[data-ubic-modo]");
        var inputLat = bloque.querySelector("[name='latitud_entrada']");
        var inputLon = bloque.querySelector("[name='longitud_entrada']");
        var resumenTexto = bloque.querySelector("[data-ubic-resumen-texto]");
        var resumenOrigen = bloque.querySelector("[data-ubic-resumen-origen]");
        var botonAbrir = bloque.querySelector("[data-ubic-abrir]");
        var panel = bloque.querySelector("[data-ubic-panel]");
        var errorPanel = bloque.querySelector("[data-ubic-error-panel]");
        var contenedorMapa = bloque.querySelector("[data-ubic-mapa]");
        var avisoTeselas = bloque.querySelector("[data-ubic-aviso-teselas]");
        var botonQuitar = bloque.querySelector("[data-ubic-quitar]");
        var botonCancelar = bloque.querySelector("[data-ubic-cancelar]");
        var botonConfirmar = bloque.querySelector("[data-ubic-confirmar]");

        var mapa = null;
        var marcador = null;
        var instantanea = null;
        var localidadPin = bloque.dataset.sedeTienePin === "1" ? (bloque.dataset.sedeLocalidad || "") : "";

        function localidadSeleccionada() {
            if (!formulario) return bloque.dataset.sedeLocalidad || "";
            var selectLoc = formulario.querySelector("[name='localidad_codigo']");
            if (selectLoc && selectLoc.value) return selectLoc.value;
            return bloque.dataset.sedeLocalidad || "";
        }

        function referenciaGeoref() {
            if (!formulario) return null;
            var bloqueDir = formulario.querySelector("[data-sede-direccion]");
            if (!bloqueDir) return null;
            var lat = parsearCoordenada(bloqueDir.dataset.georefLat);
            var lon = parsearCoordenada(bloqueDir.dataset.georefLon);
            var loc = bloqueDir.dataset.georefLocalidad || "";
            if (lat === null || lon === null || !loc) return null;
            return { lat: lat, lon: lon, localidad: loc };
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

        function limpiarErroresServidorPanel() {
            panel.querySelectorAll(".error-campo").forEach(function (el) {
                el.remove();
            });
            panel.querySelectorAll("[aria-invalid='true']").forEach(function (el) {
                el.removeAttribute("aria-invalid");
                el.removeAttribute("aria-describedby");
            });
        }

        function liberarMapa() {
            if (mapa) {
                try {
                    mapa.remove();
                } catch (error) {
                    // Ya liberado.
                }
                mapa = null;
                marcador = null;
            }
            if (contenedorMapa) {
                destruirMapaEn(contenedorMapa);
                contenedorMapa.innerHTML = "";
            }
        }

        function colocarMarcador(lat, lon, centrar) {
            if (!mapa || typeof window.L === "undefined") return;
            if (!marcador) {
                marcador = window.L.marker([lat, lon], {
                    draggable: true,
                    icon: crearIconoPin(bloque),
                }).addTo(mapa);
                marcador.on("dragend", function () {
                    var pos = marcador.getLatLng();
                    actualizarDesdeMapa(pos.lat, pos.lng);
                });
            } else {
                marcador.setLatLng([lat, lon]);
            }
            if (centrar) {
                mapa.setView([lat, lon], Math.max(mapa.getZoom(), 16));
            }
        }

        function actualizarDesdeMapa(lat, lon) {
            mostrarErrorPanel("");
            limpiarErroresServidorPanel();
            inputLat.value = formatearCoordenada(lat);
            inputLon.value = formatearCoordenada(lon);
            inputModo.value = "marcar";
            localidadPin = localidadSeleccionada();
            if (botonQuitar) botonQuitar.hidden = false;
            colocarMarcador(lat, lon, false);
        }

        function calcularCentroInicial() {
            var loc = localidadSeleccionada();
            var latActual = parsearCoordenada(inputLat.value);
            var lonActual = parsearCoordenada(inputLon.value);
            var tienePinValido = (
                latActual !== null
                && lonActual !== null
                && latActual >= -90 && latActual <= 90
                && lonActual >= -180 && lonActual <= 180
            );

            // 1. Pin guardado o marcado de la localidad seleccionada.
            if (tienePinValido && (!loc || !localidadPin || localidadPin === loc)) {
                return { lat: latActual, lon: lonActual, zoom: 16, mostrarPin: true };
            }

            // 2. Ubicación aproximada de Georef si pertenece a la localidad seleccionada.
            var georef = referenciaGeoref();
            if (georef && georef.localidad === loc) {
                return { lat: georef.lat, lon: georef.lon, zoom: 16, mostrarPin: tienePinValido };
            }

            // 3. Centro de la localidad seleccionada.
            if (loc && centros[loc]) {
                return { lat: centros[loc].lat, lon: centros[loc].lon, zoom: 13, mostrarPin: tienePinValido };
            }

            // 4. Respaldo general sobre Ciudad de Salta.
            var salta = centros["66028050"] || { lat: -24.793245, lon: -65.413746 };
            return { lat: salta.lat, lon: salta.lon, zoom: 12, mostrarPin: tienePinValido };
        }

        function inicializarMapa() {
            liberarMapa();
            if (avisoTeselas) avisoTeselas.hidden = true;

            if (typeof window.L === "undefined") {
                if (avisoTeselas) avisoTeselas.hidden = false;
                return;
            }

            var inicial = calcularCentroInicial();
            mapa = window.L.map(contenedorMapa, {
                center: [inicial.lat, inicial.lon],
                zoom: inicial.zoom,
                maxZoom: zoomMax,
            });
            instanciasActivas.set(contenedorMapa, mapa);

            var capa = window.L.tileLayer(teselasUrl, {
                maxZoom: zoomMax,
                attribution: atribucion,
                referrerPolicy: "strict-origin-when-cross-origin",
            });
            capa.on("tileerror", function () {
                if (avisoTeselas) avisoTeselas.hidden = false;
            });
            capa.addTo(mapa);

            var latActual = parsearCoordenada(inputLat.value);
            var lonActual = parsearCoordenada(inputLon.value);
            if (inicial.mostrarPin && latActual !== null && lonActual !== null) {
                colocarMarcador(latActual, lonActual, false);
            }

            mapa.on("click", function (evento) {
                actualizarDesdeMapa(evento.latlng.lat, evento.latlng.lng);
            });

            window.requestAnimationFrame(function () {
                if (mapa) mapa.invalidateSize();
            });
        }

        function guardarInstantanea() {
            instantanea = {
                modo: inputModo.value,
                lat: inputLat.value,
                lon: inputLon.value,
                localidadPin: localidadPin,
                resumenTexto: resumenTexto.textContent,
                resumenVacio: resumenTexto.classList.contains("texto-secundario"),
                resumenOrigenOculto: resumenOrigen.hidden,
                botonTexto: botonAbrir.textContent,
                quitarOculto: botonQuitar ? botonQuitar.hidden : true,
            };
        }

        function restaurarInstantanea() {
            if (!instantanea) return;
            inputModo.value = instantanea.modo;
            inputLat.value = instantanea.lat;
            inputLon.value = instantanea.lon;
            localidadPin = instantanea.localidadPin;
            resumenTexto.textContent = instantanea.resumenTexto;
            resumenTexto.classList.toggle("texto-secundario", instantanea.resumenVacio);
            resumenOrigen.hidden = instantanea.resumenOrigenOculto;
            botonAbrir.textContent = instantanea.botonTexto;
            if (botonQuitar) botonQuitar.hidden = instantanea.quitarOculto;
            instantanea = null;
        }

        function abrirPanel() {
            guardarInstantanea();
            mostrarErrorPanel("");
            panel.hidden = false;
            botonAbrir.hidden = true;
            botonAbrir.setAttribute("aria-expanded", "true");
            if (resumenTexto.classList.contains("texto-secundario")) {
                resumenTexto.hidden = true;
            }
            window.requestAnimationFrame(function () {
                inicializarMapa();
            });
        }

        function cerrarPanel(devolverFoco) {
            liberarMapa();
            panel.hidden = true;
            botonAbrir.hidden = false;
            botonAbrir.setAttribute("aria-expanded", "false");
            resumenTexto.hidden = false;
            mostrarErrorPanel("");
            if (devolverFoco && botonAbrir) {
                botonAbrir.focus();
            }
        }

        function sincronizarDesdeEntradas() {
            mostrarErrorPanel("");
            var lat = parsearCoordenada(inputLat.value);
            var lon = parsearCoordenada(inputLon.value);
            if (!inputLat.value.trim() && !inputLon.value.trim()) {
                inputModo.value = "quitar";
                if (marcador && mapa) {
                    mapa.removeLayer(marcador);
                    marcador = null;
                }
                if (botonQuitar) botonQuitar.hidden = true;
                return;
            }
            inputModo.value = "marcar";
            if (botonQuitar) botonQuitar.hidden = false;
            if (
                lat !== null && lon !== null
                && lat >= -90 && lat <= 90
                && lon >= -180 && lon <= 180
            ) {
                localidadPin = localidadSeleccionada();
                colocarMarcador(lat, lon, true);
            }
        }

        botonAbrir.addEventListener("click", abrirPanel);

        inputLat.addEventListener("input", sincronizarDesdeEntradas);
        inputLon.addEventListener("input", sincronizarDesdeEntradas);

        if (botonQuitar) {
            botonQuitar.addEventListener("click", function () {
                mostrarErrorPanel("");
                limpiarErroresServidorPanel();
                inputLat.value = "";
                inputLon.value = "";
                inputModo.value = "quitar";
                localidadPin = "";
                if (marcador && mapa) {
                    mapa.removeLayer(marcador);
                    marcador = null;
                }
                botonQuitar.hidden = true;
            });
        }

        botonCancelar.addEventListener("click", function () {
            restaurarInstantanea();
            cerrarPanel(true);
        });

        botonConfirmar.addEventListener("click", function () {
            mostrarErrorPanel("");
            var latTxt = inputLat.value.trim();
            var lonTxt = inputLon.value.trim();

            if (!latTxt && !lonTxt) {
                inputModo.value = "quitar";
                localidadPin = "";
                resumenTexto.textContent = "Sin ubicación marcada";
                resumenTexto.classList.add("texto-secundario");
                resumenOrigen.hidden = true;
                botonAbrir.textContent = "Marcar ubicación";
                instantanea = null;
                cerrarPanel(true);
                return;
            }

            if (!latTxt || !lonTxt) {
                mostrarErrorPanel("Ingresá tanto la latitud como la longitud, o dejá ambos campos vacíos.");
                (latTxt ? inputLon : inputLat).focus();
                return;
            }

            var lat = parsearCoordenada(latTxt);
            var lon = parsearCoordenada(lonTxt);
            if (lat !== null && lon !== null) {
                inputLat.value = formatearCoordenada(lat);
                inputLon.value = formatearCoordenada(lon);
            }
            inputModo.value = "marcar";
            localidadPin = localidadSeleccionada();
            resumenTexto.textContent = "Lat " + inputLat.value.trim() + ", Lon " + inputLon.value.trim();
            resumenTexto.classList.remove("texto-secundario");
            resumenOrigen.hidden = false;
            botonAbrir.textContent = "Cambiar ubicación";
            instantanea = null;
            cerrarPanel(true);
        });

        if (formulario) {
            formulario.addEventListener("sede-direccion:cambio", function () {
                if (!panel.hidden && mapa) {
                    var centro = calcularCentroInicial();
                    mapa.setView([centro.lat, centro.lon], centro.zoom);
                }
            });
        }

        if (dialogo && !dialogo.dataset.sedeUbicacionCierreRegistrado) {
            dialogo.dataset.sedeUbicacionCierreRegistrado = "true";
            dialogo.addEventListener("close", function () {
                dialogo.querySelectorAll("[data-ubic-mapa]").forEach(destruirMapaEn);
            });
        }

        if (!panel.hidden) {
            guardarInstantanea();
            window.requestAnimationFrame(function () {
                inicializarMapa();
            });
        }
    }

    function prepararEn(raiz) {
        raiz.querySelectorAll("[data-ubic-mapa]").forEach(destruirMapaEn);
        raiz.querySelectorAll("[data-sede-ubicacion]").forEach(prepararBloque);
    }

    prepararEn(document);
    document.addEventListener("modal-formulario:cargado", function (evento) {
        prepararEn(evento.target);
    });
});
