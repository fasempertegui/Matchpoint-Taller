(function () {
    var SVG_NS = "http://www.w3.org/2000/svg";
    var DURACIONES = {
        success: 5000,
        info: 5000,
        warning: 8000,
        error: 0,
    };
    var SELECTOR_ENFOCABLE = [
        "button:not(:disabled)",
        "a[href]",
        "input:not([type='hidden']):not(:disabled)",
        "select:not(:disabled)",
        "textarea:not(:disabled)",
        "[tabindex]:not([tabindex='-1'])",
    ].join(", ");

    var controladores = new WeakMap();
    var pilaModales = [];
    var contenedor = null;
    var lista = null;
    var anuncioEstado = null;
    var anuncioAlerta = null;
    var ultimoFocoPrevio = null;
    var cargaInicialAsentada = false;
    var framesAnuncio = { status: 0, alert: 0 };
    var inicializado = false;

    function normalizarNivel(nivel) {
        if (nivel === "success" || nivel === "info" || nivel === "warning" || nivel === "error") {
            return nivel;
        }
        return "info";
    }

    function crearSvg(tamano, grosor, elementos) {
        var svg = document.createElementNS(SVG_NS, "svg");
        svg.setAttribute("aria-hidden", "true");
        svg.setAttribute("focusable", "false");
        svg.setAttribute("width", String(tamano));
        svg.setAttribute("height", String(tamano));
        svg.setAttribute("viewBox", "0 0 24 24");
        svg.setAttribute("fill", "none");
        svg.setAttribute("stroke", "currentColor");
        svg.setAttribute("stroke-width", String(grosor));
        svg.setAttribute("stroke-linecap", "round");
        svg.setAttribute("stroke-linejoin", "round");

        elementos.forEach(function (item) {
            var nodo = document.createElementNS(SVG_NS, item.tag);
            Object.keys(item.attrs).forEach(function (clave) {
                nodo.setAttribute(clave, item.attrs[clave]);
            });
            svg.append(nodo);
        });
        return svg;
    }

    function crearIconoNivel(nivel) {
        if (nivel === "success") {
            return crearSvg(18, 1.75, [
                { tag: "circle", attrs: { cx: "12", cy: "12", r: "9" } },
                { tag: "path", attrs: { d: "m8.5 12.5 2.5 2.5 4.5-5" } },
            ]);
        }
        if (nivel === "error") {
            return crearSvg(18, 1.75, [
                { tag: "circle", attrs: { cx: "12", cy: "12", r: "9" } },
                { tag: "path", attrs: { d: "M12 8v5" } },
                { tag: "path", attrs: { d: "M12 16.5h.01" } },
            ]);
        }
        if (nivel === "warning") {
            return crearSvg(18, 1.75, [
                { tag: "path", attrs: { d: "M12 9v4" } },
                { tag: "path", attrs: { d: "M12 17h.01" } },
                { tag: "path", attrs: { d: "M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z" } },
            ]);
        }
        return crearSvg(18, 1.75, [
            { tag: "circle", attrs: { cx: "12", cy: "12", r: "9" } },
            { tag: "path", attrs: { d: "M12 11.5v4.5" } },
            { tag: "path", attrs: { d: "M12 8h.01" } },
        ]);
    }

    function crearIconoCruz() {
        return crearSvg(24, 1.5, [
            { tag: "path", attrs: { d: "M6.75827 17.2426L12.0009 12M17.2435 6.75736L12.0009 12M12.0009 12L6.75827 6.75736M12.0009 12L17.2435 17.2426" } },
        ]);
    }

    function asegurarContenedor() {
        if (contenedor && contenedor.isConnected) return contenedor;

        contenedor = document.querySelector("[data-toasts]");
        if (!contenedor) {
            contenedor = document.createElement("section");
            contenedor.className = "toasts";
            contenedor.setAttribute("aria-label", "Avisos del sistema");
            contenedor.setAttribute("data-toasts", "");

            anuncioEstado = document.createElement("div");
            anuncioEstado.className = "toast-solo-lector";
            anuncioEstado.setAttribute("role", "status");
            anuncioEstado.setAttribute("aria-live", "polite");
            anuncioEstado.setAttribute("aria-atomic", "true");
            anuncioEstado.setAttribute("data-toast-anuncio-estado", "");

            anuncioAlerta = document.createElement("div");
            anuncioAlerta.className = "toast-solo-lector";
            anuncioAlerta.setAttribute("role", "alert");
            anuncioAlerta.setAttribute("aria-live", "assertive");
            anuncioAlerta.setAttribute("aria-atomic", "true");
            anuncioAlerta.setAttribute("data-toast-anuncio-alerta", "");

            lista = document.createElement("div");
            lista.className = "toasts-lista";
            lista.setAttribute("data-toasts-lista", "");

            contenedor.append(anuncioEstado, anuncioAlerta, lista);
            document.body.append(contenedor);
        } else {
            anuncioEstado = contenedor.querySelector("[data-toast-anuncio-estado]");
            anuncioAlerta = contenedor.querySelector("[data-toast-anuncio-alerta]");
            lista = contenedor.querySelector("[data-toasts-lista]");
        }

        if (!contenedor.dataset.toastsConectado) {
            contenedor.dataset.toastsConectado = "1";
            contenedor.addEventListener("focusin", function (evento) {
                var previo = evento.relatedTarget;
                if (previo instanceof HTMLElement && !contenedor.contains(previo)) {
                    ultimoFocoPrevio = previo;
                }
            });
        }
        return contenedor;
    }

    function anunciar(texto, nivel) {
        asegurarContenedor();
        var clave = nivel === "error" ? "alert" : "status";
        var region = clave === "alert" ? anuncioAlerta : anuncioEstado;
        if (!region) return;

        if (framesAnuncio[clave]) {
            window.cancelAnimationFrame(framesAnuncio[clave]);
        }
        region.textContent = "";
        framesAnuncio[clave] = window.requestAnimationFrame(function () {
            framesAnuncio[clave] = window.requestAnimationFrame(function () {
                framesAnuncio[clave] = 0;
                region.textContent = texto;
            });
        });
    }

    function esDialogoModalAbierto(elemento) {
        return elemento instanceof HTMLDialogElement && elemento.isConnected && elemento.open && elemento.matches(":modal");
    }

    function limpiarRolesServidorAnunciados() {
        if (!cargaInicialAsentada || !lista) return;
        lista.querySelectorAll("[data-toast-servidor] .toast-texto[role]").forEach(function (texto) {
            texto.removeAttribute("role");
        });
    }

    function actualizarPilaDialogos(candidato) {
        pilaModales = pilaModales.filter(esDialogoModalAbierto);
        if (candidato && esDialogoModalAbierto(candidato)) {
            pilaModales = pilaModales.filter(function (dialogo) { return dialogo !== candidato; });
            pilaModales.push(candidato);
        }
        document.querySelectorAll("dialog[open]").forEach(function (dialogo) {
            if (esDialogoModalAbierto(dialogo) && pilaModales.indexOf(dialogo) === -1) {
                pilaModales.push(dialogo);
            }
        });
    }

    function sincronizarContenedor(candidato) {
        asegurarContenedor();
        actualizarPilaDialogos(candidato);

        var destino = pilaModales.length ? pilaModales[pilaModales.length - 1] : document.body;
        if (!destino || contenedor.parentNode === destino) return;

        var focoActivo = contenedor.contains(document.activeElement) ? document.activeElement : null;
        // Evita reanunciar mensajes del servidor al mover la pila hacia o desde un diálogo posterior.
        limpiarRolesServidorAnunciados();
        destino.append(contenedor);
        if (focoActivo && focoActivo.isConnected) {
            focoActivo.focus({ preventScroll: true });
        }
    }

    function desmontarDe(dialogo) {
        if (!contenedor || !dialogo || !dialogo.contains(contenedor)) return;
        limpiarRolesServidorAnunciados();
        document.body.append(contenedor);
    }

    function enfocarAlCerrar(toast) {
        if (!toast.contains(document.activeElement)) return;

        var candidatos = [toast.nextElementSibling, toast.previousElementSibling];
        for (var i = 0; i < candidatos.length; i++) {
            var hermano = candidatos[i];
            if (hermano && !hermano.classList.contains("toast-saliendo")) {
                var botonHermano = hermano.querySelector(".toast-cerrar:not([hidden])");
                if (botonHermano) {
                    botonHermano.focus({ preventScroll: true });
                    return;
                }
            }
        }

        var dialogo = toast.closest("dialog[open]");
        if (dialogo) {
            if (ultimoFocoPrevio && dialogo.contains(ultimoFocoPrevio) && !contenedor.contains(ultimoFocoPrevio)) {
                ultimoFocoPrevio.focus({ preventScroll: true });
                return;
            }
            var controles = dialogo.querySelectorAll(SELECTOR_ENFOCABLE);
            for (var j = 0; j < controles.length; j++) {
                if (!contenedor.contains(controles[j])) {
                    controles[j].focus({ preventScroll: true });
                    return;
                }
            }
            return;
        }

        if (ultimoFocoPrevio && ultimoFocoPrevio.isConnected && !contenedor.contains(ultimoFocoPrevio)) {
            ultimoFocoPrevio.focus({ preventScroll: true });
        }
    }

    function conectarToast(toast) {
        if (controladores.has(toast)) return controladores.get(toast);

        var boton = toast.querySelector(".toast-cerrar");
        var nivelInicial = normalizarNivel(toast.dataset.toastNivel);
        var duracionAtributo = Number(toast.dataset.autocierre);
        var duracion = Number.isFinite(duracionAtributo) && duracionAtributo > 0
            ? duracionAtributo
            : DURACIONES[nivelInicial];
        var restante = duracion;
        var temporizador = null;
        var iniciadoEn = null;
        var cerrando = false;

        function limpiarTemporizador() {
            if (temporizador !== null) {
                window.clearTimeout(temporizador);
                temporizador = null;
            }
            iniciadoEn = null;
        }

        function cerrar() {
            if (cerrando) return;
            cerrando = true;
            limpiarTemporizador();
            enfocarAlCerrar(toast);
            toast.classList.add("toast-saliendo");
            var demora = window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 180;
            window.setTimeout(function () {
                toast.remove();
            }, demora);
        }

        function estaPausado() {
            return toast.matches(":hover") || toast.contains(document.activeElement);
        }

        function pausar() {
            if (temporizador !== null) {
                window.clearTimeout(temporizador);
                restante = Math.max(0, restante - (performance.now() - iniciadoEn));
                temporizador = null;
                iniciadoEn = null;
            }
        }

        function vencer() {
            temporizador = null;
            restante = Math.max(0, restante - (performance.now() - iniciadoEn));
            iniciadoEn = null;
            if (estaPausado()) return;
            cerrar();
        }

        function actualizar() {
            if (cerrando || duracion <= 0) return;
            pausar();
            if (estaPausado()) return;
            if (restante <= 0) {
                cerrar();
                return;
            }
            iniciadoEn = performance.now();
            temporizador = window.setTimeout(vencer, restante);
        }

        function actualizarContenido(texto, nuevoNivel) {
            if (cerrando) return false;
            var nivelNormalizado = normalizarNivel(nuevoNivel);
            toast.classList.remove("toast-success", "toast-info", "toast-warning", "toast-error");
            toast.classList.add("toast-" + nivelNormalizado);
            toast.dataset.toastNivel = nivelNormalizado;

            var iconoContenedor = toast.querySelector(".toast-icono");
            if (iconoContenedor) {
                iconoContenedor.replaceChildren(crearIconoNivel(nivelNormalizado));
            }
            var textoNodo = toast.querySelector(".toast-texto");
            if (textoNodo) {
                textoNodo.textContent = texto;
            }

            limpiarTemporizador();
            duracion = DURACIONES[nivelNormalizado];
            restante = duracion;
            if (duracion > 0) {
                toast.dataset.autocierre = String(duracion);
                actualizar();
            } else {
                delete toast.dataset.autocierre;
            }
            return true;
        }

        if (boton) {
            boton.hidden = false;
            boton.addEventListener("click", cerrar);
        }

        toast.addEventListener("mouseenter", actualizar);
        toast.addEventListener("mouseleave", actualizar);
        toast.addEventListener("focusin", actualizar);
        toast.addEventListener("focusout", function () {
            window.setTimeout(actualizar, 0);
        });

        if (duracion > 0) {
            actualizar();
        }

        var api = {
            cerrar: cerrar,
            actualizarContenido: actualizarContenido,
            estaCerrando: function () { return cerrando; },
        };
        controladores.set(toast, api);
        return api;
    }

    function crearElementoToast(texto, nivel, clave) {
        var toast = document.createElement("div");
        toast.className = "toast toast-" + nivel;
        toast.setAttribute("data-toast", "");
        toast.dataset.toastNivel = nivel;
        if (DURACIONES[nivel] > 0) {
            toast.dataset.autocierre = String(DURACIONES[nivel]);
        }
        if (clave) {
            toast.dataset.toastClave = clave;
        }

        var icono = document.createElement("span");
        icono.className = "toast-icono";
        icono.setAttribute("aria-hidden", "true");
        icono.append(crearIconoNivel(nivel));

        var parrafo = document.createElement("p");
        parrafo.className = "toast-texto";
        parrafo.textContent = texto;

        var boton = document.createElement("button");
        boton.type = "button";
        boton.className = "toast-cerrar";
        boton.setAttribute("aria-label", "Cerrar aviso");
        boton.append(crearIconoCruz());

        toast.append(icono, parrafo, boton);
        return toast;
    }

    function mostrar(opciones) {
        var configuracion = typeof opciones === "string" ? { texto: opciones } : (opciones || {});
        var texto = String(configuracion.texto || "").trim();
        if (!texto) return null;

        var nivel = normalizarNivel(configuracion.nivel);
        var clave = configuracion.clave ? String(configuracion.clave) : "";

        asegurarContenedor();
        sincronizarContenedor();

        if (clave && lista) {
            var existentes = lista.querySelectorAll("[data-toast-clave]");
            for (var i = 0; i < existentes.length; i++) {
                var existente = existentes[i];
                if (existente.dataset.toastClave === clave) {
                    var controlador = controladores.get(existente);
                    if (controlador && !controlador.estaCerrando() && controlador.actualizarContenido(texto, nivel)) {
                        anunciar(texto, nivel);
                        return existente;
                    }
                }
            }
        }

        var toast = crearElementoToast(texto, nivel, clave);
        lista.append(toast);
        conectarToast(toast);
        anunciar(texto, nivel);
        return toast;
    }

    function inicializar() {
        if (inicializado) return;
        inicializado = true;

        asegurarContenedor();
        if (lista) {
            lista.querySelectorAll("[data-toast]").forEach(conectarToast);
        }
        sincronizarContenedor();

        var observador = new MutationObserver(function (mutaciones) {
            var candidato = null;
            var huboCambio = false;
            mutaciones.forEach(function (mutacion) {
                if (mutacion.target instanceof HTMLDialogElement) {
                    huboCambio = true;
                    if (mutacion.target.open) candidato = mutacion.target;
                }
            });
            if (huboCambio) {
                sincronizarContenedor(candidato);
            }
        });
        observador.observe(document.documentElement, {
            attributes: true,
            attributeFilter: ["open"],
            subtree: true,
        });

        window.setTimeout(function () {
            cargaInicialAsentada = true;
        }, 1000);
    }

    window.Mensajes = {
        mostrar: mostrar,
        sincronizarContenedor: sincronizarContenedor,
        desmontarDe: desmontarDe,
    };
    window.mostrarToast = mostrar;

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", inicializar);
    } else {
        inicializar();
    }
})();
