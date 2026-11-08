document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-usuario-selector]").forEach(function (selector) {
        var entrada = selector.querySelector("[data-usuario-busqueda]");
        var multiple = selector.hasAttribute("data-usuario-multiple");
        var campo = selector.querySelector('input[type="hidden"]');
        var seleccion = selector.querySelector("[data-usuario-seleccion]");
        var buscador = selector.querySelector("[data-usuario-buscador]");
        var nombre = selector.querySelector("[data-usuario-nombre]");
        var usuario = selector.querySelector("[data-usuario-usuario]");
        var resultados = selector.querySelector("[data-usuario-resultados]");
        var estado = selector.querySelector("[data-estado]");
        var solicitud = null;
        var demora = null;

        function limpiarBusqueda() {
            window.clearTimeout(demora);
            if (solicitud) solicitud.abort();
            resultados.replaceChildren();
            resultados.hidden = true;
            estado.textContent = "";
        }

        function quitar() {
            limpiarBusqueda();
            campo.value = "";
            nombre.textContent = "";
            usuario.textContent = "";
            entrada.value = "";
            seleccion.hidden = true;
            buscador.hidden = false;
        }

        function elegir(persona) {
            limpiarBusqueda();
            if (multiple) {
                if (Array.from(seleccion.querySelectorAll("input")).some(function (valor) { return valor.value === String(persona.id); })) return;
                var fila = document.createElement("li");
                var texto = document.createElement("span");
                texto.textContent = persona.nombre;
                var detalle = document.createElement("small");
                detalle.textContent = persona.usuario;
                texto.append(detalle);
                var valor = document.createElement("input");
                valor.type = "hidden";
                valor.name = selector.dataset.campo;
                valor.value = persona.id;
                var boton = document.createElement("button");
                boton.type = "button";
                boton.className = "clase-quitar";
                boton.dataset.usuarioQuitar = "";
                boton.setAttribute("aria-label", "Quitar a " + persona.nombre);
                boton.textContent = "×";
                fila.append(texto, valor, boton);
                seleccion.append(fila);
                seleccion.hidden = false;
                selector.querySelector("[data-usuario-vacio]").hidden = true;
                entrada.value = "";
                entrada.focus();
                return;
            }
            campo.value = persona.id;
            nombre.textContent = persona.nombre;
            usuario.textContent = persona.usuario;
            entrada.value = "";
            seleccion.hidden = false;
            buscador.hidden = true;
            selector.querySelector("[data-usuario-quitar]").focus();
        }

        async function buscar() {
            var texto = entrada.value.trim();
            if (texto.length < 2 || !selector.isConnected) return;
            var actual = new AbortController();
            solicitud = actual;
            estado.textContent = "Buscando…";
            var url = new URL(selector.dataset.url, window.location.origin);
            url.searchParams.set("q", texto);
            if (multiple) seleccion.querySelectorAll("input").forEach(function (valor) { url.searchParams.append("excluir", valor.value); });
            try {
                var respuesta = await fetch(url, {signal: actual.signal, credentials: "same-origin", cache: "no-store"});
                if (!respuesta.ok || respuesta.redirected) throw new Error();
                var datos = await respuesta.json();
                if (solicitud !== actual || entrada.value.trim() !== texto || !selector.isConnected) return;
                resultados.replaceChildren();
                datos.resultados.forEach(function (persona) {
                    var fila = document.createElement("li");
                    var boton = document.createElement("button");
                    boton.type = "button";
                    boton.textContent = persona.nombre;
                    var detalle = document.createElement("small");
                    detalle.textContent = persona.usuario;
                    boton.append(detalle);
                    boton.addEventListener("click", function () { elegir(persona); });
                    fila.append(boton);
                    resultados.append(fila);
                });
                resultados.hidden = datos.resultados.length === 0;
                estado.textContent = datos.resultados.length ? datos.resultados.length + " coincidencias. Elegí una para agregar." : "Sin coincidencias disponibles.";
                if (datos.hay_mas) estado.textContent += " Hay más resultados: precisá la búsqueda.";
            } catch (error) {
                if (error.name !== "AbortError" && solicitud === actual && selector.isConnected) {
                    estado.textContent = "No se pudo buscar. Volvé a escribir o recargá la página si tu sesión venció.";
                }
            }
        }

        entrada.addEventListener("input", function () {
            limpiarBusqueda();
            if (entrada.value.trim().length >= 2) demora = window.setTimeout(buscar, 250);
        });
        if (multiple) {
            var alternar = selector.querySelector("[data-usuario-alternar]");
            alternar.addEventListener("click", function () {
                buscador.hidden = !buscador.hidden;
                alternar.setAttribute("aria-expanded", String(!buscador.hidden));
                alternar.setAttribute("aria-label", buscador.hidden ? "Agregar invitados" : "Cerrar buscador");
                if (buscador.hidden) {
                    limpiarBusqueda();
                    entrada.value = "";
                } else {
                    entrada.focus();
                }
            });
            seleccion.addEventListener("click", function (evento) {
                var boton = evento.target.closest("[data-usuario-quitar]");
                if (!boton) return;
                boton.closest("li").remove();
                limpiarBusqueda();
                seleccion.hidden = seleccion.children.length === 0;
                selector.querySelector("[data-usuario-vacio]").hidden = !seleccion.hidden;
                if (buscador.hidden) alternar.focus();
                else entrada.focus();
            });
        } else {
            selector.querySelector("[data-usuario-quitar]").addEventListener("click", function () {
                quitar();
                entrada.focus();
            });
            selector.addEventListener("usuario:limpiar", quitar);
        }
        selector.addEventListener("keydown", function (evento) {
            var botones = Array.from(resultados.querySelectorAll("button"));
            var indice = botones.indexOf(document.activeElement);
            if (evento.key === "ArrowDown" && botones.length) {
                evento.preventDefault();
                botones[(indice + 1) % botones.length].focus();
            } else if (evento.key === "ArrowUp" && indice >= 0) {
                evento.preventDefault();
                if (indice === 0) entrada.focus();
                else botones[indice - 1].focus();
            } else if (evento.key === "Escape") {
                limpiarBusqueda();
                if (!buscador.hidden) entrada.focus();
            } else if (evento.key === "Enter" && evento.target === entrada) {
                evento.preventDefault();
                if (botones.length) botones[0].focus();
            }
        });
    });
});
