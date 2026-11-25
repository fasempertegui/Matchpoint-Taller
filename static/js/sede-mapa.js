document.addEventListener("DOMContentLoaded", function () {
    function crearIcono(el) {
        if (typeof window.L === "undefined") return undefined;
        return window.L.icon({
            iconUrl: el.dataset.markerIcon,
            iconRetinaUrl: el.dataset.markerIcon2x,
            shadowUrl: el.dataset.markerShadow,
            iconSize: [25, 41],
            iconAnchor: [12, 41],
            popupAnchor: [1, -34],
            shadowSize: [41, 41],
        });
    }

    function montarMapaLectura(contenedor, opciones) {
        if (typeof window.L === "undefined") {
            if (opciones.avisoTeselas) opciones.avisoTeselas.hidden = false;
            return null;
        }
        var mapa = window.L.map(contenedor, {
            center: [opciones.lat, opciones.lon],
            zoom: 16,
            maxZoom: opciones.zoomMax || 19,
            scrollWheelZoom: false,
        });
        var capa = window.L.tileLayer(opciones.teselasUrl, {
            maxZoom: opciones.zoomMax || 19,
            attribution: opciones.atribucion,
            referrerPolicy: "strict-origin-when-cross-origin",
        });
        capa.on("tileerror", function () {
            if (opciones.avisoTeselas) opciones.avisoTeselas.hidden = false;
        });
        capa.addTo(mapa);
        window.L.marker([opciones.lat, opciones.lon], {
            icon: crearIcono(opciones.fuenteIconos),
        }).addTo(mapa);
        return mapa;
    }

    // 1. Minimapa de solo lectura en el detalle administrativo.
    document.querySelectorAll("[data-sede-minimapa]").forEach(function (contenedor) {
        var lat = Number(contenedor.dataset.lat);
        var lon = Number(contenedor.dataset.lon);
        if (!Number.isFinite(lat) || !Number.isFinite(lon)) return;

        var aviso = contenedor.parentElement.querySelector("[data-mapa-aviso-teselas]");
        var mapa = montarMapaLectura(contenedor, {
            lat: lat,
            lon: lon,
            teselasUrl: contenedor.dataset.teselasUrl,
            atribucion: contenedor.dataset.atribucion,
            zoomMax: parseInt(contenedor.dataset.zoomMax || "19", 10) || 19,
            avisoTeselas: aviso,
            fuenteIconos: contenedor,
        });

        var pestanaDetalles = document.getElementById("sede-tab-detalles");
        if (pestanaDetalles && mapa) {
            pestanaDetalles.addEventListener("click", function () {
                window.requestAnimationFrame(function () {
                    mapa.invalidateSize();
                });
            });
        }
    });

    // 2. Panel compartido de ubicación en el catálogo de sedes.
    var modal = document.querySelector("[data-sede-mapa-modal]");
    if (!modal) return;

    var titulo = modal.querySelector("[data-sede-mapa-titulo]");
    var direccion = modal.querySelector("[data-sede-mapa-direccion]");
    var bloqueMapa = modal.querySelector("[data-sede-mapa-bloque]");
    var contenedorMapa = modal.querySelector("[data-sede-mapa-canvas]");
    var avisoTeselas = modal.querySelector("[data-mapa-aviso-teselas]");
    var sinPin = modal.querySelector("[data-sede-mapa-sin-pin]");
    var enlacesBloque = modal.querySelector("[data-sede-mapa-enlaces]");
    var enlaceComoLlegar = modal.querySelector("[data-sede-mapa-como-llegar]");
    var enlaceAgenda = modal.querySelector("[data-sede-mapa-agenda]");

    var mapaModal = null;
    var disparadorActual = null;

    function liberarMapaModal() {
        if (mapaModal) {
            try {
                mapaModal.remove();
            } catch (error) {
                // Ya liberado.
            }
            mapaModal = null;
        }
        if (contenedorMapa) {
            contenedorMapa.innerHTML = "";
        }
    }

    document.addEventListener("click", function (evento) {
        var boton = evento.target.closest("[data-ver-ubicacion-sede]");
        if (!boton) return;

        liberarMapaModal();
        var menu = boton.closest("details[data-menu-contextual]");
        if (menu) menu.open = false;
        disparadorActual = menu ? (menu.querySelector("summary") || boton) : boton;

        titulo.textContent = boton.dataset.sedeNombre || "Ubicación de la sede";
        direccion.textContent = boton.dataset.sedeDireccion || "Dirección sin informar";
        if (avisoTeselas) avisoTeselas.hidden = true;

        var lat = boton.dataset.sedeLat ? Number(boton.dataset.sedeLat) : NaN;
        var lon = boton.dataset.sedeLon ? Number(boton.dataset.sedeLon) : NaN;
        var tienePin = Number.isFinite(lat) && Number.isFinite(lon);

        bloqueMapa.hidden = !tienePin;
        sinPin.hidden = tienePin;
        enlacesBloque.hidden = !tienePin;

        if (tienePin) {
            enlaceComoLlegar.href = boton.dataset.sedeUrlComoLlegar || "#";
        } else {
            enlaceComoLlegar.removeAttribute("href");
        }

        var urlAgenda = boton.dataset.sedeUrlAgenda || "";
        if (enlaceAgenda) {
            if (urlAgenda) {
                enlaceAgenda.href = urlAgenda;
                enlaceAgenda.hidden = false;
            } else {
                enlaceAgenda.removeAttribute("href");
                enlaceAgenda.hidden = true;
            }
        }

        if (!modal.open) {
            document.documentElement.classList.add("modal-abierto");
            modal.showModal();
        }
        titulo.focus();

        if (tienePin) {
            window.requestAnimationFrame(function () {
                mapaModal = montarMapaLectura(contenedorMapa, {
                    lat: lat,
                    lon: lon,
                    teselasUrl: modal.dataset.teselasUrl,
                    atribucion: modal.dataset.atribucion,
                    zoomMax: parseInt(modal.dataset.zoomMax || "19", 10) || 19,
                    avisoTeselas: avisoTeselas,
                    fuenteIconos: modal,
                });
                if (mapaModal) {
                    window.requestAnimationFrame(function () {
                        if (mapaModal) mapaModal.invalidateSize();
                    });
                }
            });
        }
    });

    modal.addEventListener("click", function (evento) {
        if (evento.target.closest("[data-sede-mapa-cerrar]")) {
            modal.close("cerrar");
        }
    });

    modal.addEventListener("close", function () {
        liberarMapaModal();
        document.documentElement.classList.remove("modal-abierto");
        var foco = disparadorActual;
        disparadorActual = null;
        if (foco && foco.isConnected) {
            foco.focus();
        }
    });
});
