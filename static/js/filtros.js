document.addEventListener("DOMContentLoaded", function () {
    var pagina = document.getElementById("contenido-principal");
    var contenido = pagina?.querySelector(".tarjeta-filtros-contenido");
    if (!contenido) return;

    var selectorFormulario = ".tarjeta-filtros-contenido > form, form[data-filtros-automaticos]";
    var selectorTexto = 'input:not([type]), input[type="text"], input[type="search"]';
    var selectorResultados = "[data-resultados-filtros]";
    var selectorEnlace = "[data-limpiar-filtros], [data-consulta-filtros]";
    var plantilla = contenido.querySelector("[data-filtro-borrar-texto]");
    var formulario = contenido.querySelector(":scope > form");
    var navegacion = formulario.hasAttribute("data-filtros-navegacion");
    var demora;
    var solicitud;

    function prepararCampos() {
        formulario.querySelectorAll(selectorTexto).forEach(function (campo) {
            var contenedor = document.createElement("div");
            contenedor.className = "filtro-campo-texto";
            var boton = plantilla.content.firstElementChild.cloneNode(true);
            boton.hidden = !campo.value;
            campo.before(contenedor);
            contenedor.append(campo, boton);
        });
    }

    function cancelarPendientes() {
        window.clearTimeout(demora);
        solicitud?.abort();
    }

    async function actualizar(url, conservarTexto, alFallar) {
        cancelarPendientes();
        var actual = new AbortController();
        solicitud = actual;

        try {
            var respuesta = await fetch(url, {signal: actual.signal, cache: "no-store"});
            if (!respuesta.ok || respuesta.redirected) throw new Error();
            var html = await respuesta.text();
            if (actual.signal.aborted) return;

            var documento = new DOMParser().parseFromString(html, "text/html");
            var nuevaPagina = documento.getElementById("contenido-principal");
            var nuevoFormulario = nuevaPagina?.querySelector(".tarjeta-filtros-contenido > form");
            var regiones = Array.from(pagina.querySelectorAll(selectorResultados));
            var nuevasRegiones = new Map(Array.from(nuevaPagina?.querySelectorAll(selectorResultados) || [], function (region) {
                return [region.dataset.resultadosFiltros, region];
            }));
            if (!nuevoFormulario || !regiones.length || regiones.length !== nuevasRegiones.size
                || regiones.some(function (region) { return !nuevasRegiones.has(region.dataset.resultadosFiltros); })) {
                throw new Error();
            }

            var activo = document.activeElement || document.body;
            var editarTexto = formulario.contains(activo) && activo.matches(selectorTexto);
            var reemplazo = activo.id ? nuevoFormulario.querySelector("#" + CSS.escape(activo.id)) : null;
            if (!reemplazo && formulario.contains(activo) && activo.name) {
                reemplazo = Array.from(nuevoFormulario.elements).find(function (campo) {
                    return campo.name === activo.name && (activo.type !== "radio" || campo.value === activo.value);
                });
            }
            if (conservarTexto && editarTexto && reemplazo) reemplazo.value = activo.value;

            window.history.replaceState(window.history.state, "", url);
            regiones.forEach(function (region) {
                region.replaceWith(nuevasRegiones.get(region.dataset.resultadosFiltros));
            });
            formulario.replaceWith(nuevoFormulario);
            formulario = nuevoFormulario;
            prepararCampos();
            formulario.dispatchEvent(new Event("filtros:actualizados", {bubbles: true}));

            if (activo.matches("[data-limpiar-filtros]")) {
                reemplazo = formulario.querySelector("[data-limpiar-filtros]");
            } else if (activo.matches("[data-consulta-filtros]")) {
                reemplazo = pagina.querySelector('[data-consulta-filtros][aria-current="page"]');
            } else if (!reemplazo && !activo.isConnected && activo.id) {
                reemplazo = document.getElementById(activo.id);
            }
            reemplazo?.focus({preventScroll: true});
            if (conservarTexto && editarTexto && activo.selectionStart !== null) {
                reemplazo?.setSelectionRange(activo.selectionStart, activo.selectionEnd, activo.selectionDirection);
            }
        } catch {
            if (actual.signal.aborted) return;
            alFallar?.();
            if (window.Mensajes) {
                window.Mensajes.mostrar({
                    texto: "No se pudieron actualizar los resultados. Volvé a intentar",
                    nivel: "error",
                    clave: "filtros-error",
                });
            }
        } finally {
            if (solicitud === actual) solicitud = null;
        }
    }

    function urlFormulario(origen) {
        var url = new URL(origen.action);
        url.search = new URLSearchParams(new FormData(origen));
        return url;
    }

    function programarEnvio(evento) {
        var campo = evento.target;
        if (campo.form !== formulario || !campo.matches(selectorTexto)) return;
        campo.nextElementSibling.hidden = !campo.value;
        cancelarPendientes();
        if (!evento.isComposing) demora = window.setTimeout(function () { formulario.requestSubmit(); }, 300);
    }

    prepararCampos();
    pagina.addEventListener("compositionstart", function (evento) {
        if (evento.target.form === formulario && evento.target.matches(selectorTexto)) cancelarPendientes();
    });
    pagina.addEventListener("compositionend", programarEnvio);
    pagina.addEventListener("input", programarEnvio);

    pagina.addEventListener("change", function (evento) {
        var campo = evento.target;
        if (campo.form?.matches(selectorFormulario)
            && campo.matches("select, input[type=radio], input[type=checkbox], input[type=date], input[type=month]")) {
            campo.form.requestSubmit();
        }
    });

    pagina.addEventListener("submit", function (evento) {
        if (evento.defaultPrevented || !evento.target.matches(selectorFormulario)) return;
        cancelarPendientes();
        if (navegacion) return;
        evento.preventDefault();
        actualizar(urlFormulario(evento.target), true);
    });

    pagina.addEventListener("click", function (evento) {
        var boton = evento.target.closest(".filtro-borrar-texto");
        if (boton?.form === formulario) {
            var campo = boton.previousElementSibling;
            var valor = campo.value;
            campo.value = "";
            boton.hidden = true;
            campo.focus({preventScroll: true});
            if (navegacion) {
                formulario.requestSubmit();
            } else {
                actualizar(urlFormulario(formulario), true, function () {
                    campo.value = valor;
                    boton.hidden = false;
                });
            }
            return;
        }

        var enlace = evento.target.closest(selectorEnlace);
        if (!enlace || evento.defaultPrevented || evento.ctrlKey || evento.metaKey || evento.shiftKey || evento.altKey) return;
        cancelarPendientes();
        if (navegacion) return;
        evento.preventDefault();
        actualizar(enlace.href, false);
    });
});
