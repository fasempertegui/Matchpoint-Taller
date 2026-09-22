document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-mensaje]").forEach(function (mensaje) {
        var boton = mensaje.querySelector(".mensaje-cerrar");
        var duracion = Number(mensaje.dataset.autocierre);
        var tieneAutocierre = Number.isFinite(duracion) && duracion > 0;
        var restante = tieneAutocierre ? duracion : 0;
        var temporizador = null;
        var iniciadoEn = null;
        var cerrando = false;

        function cerrar() {
            if (cerrando) return;
            cerrando = true;
            if (temporizador !== null) window.clearTimeout(temporizador);
            mensaje.classList.add("mensaje-saliendo");
            var demora = window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 200;
            window.setTimeout(function () {
                mensaje.remove();
                document.removeEventListener("visibilitychange", actualizar);
            }, demora);
        }

        function estaPausado() {
            return document.hidden || mensaje.matches(":hover") || mensaje.contains(document.activeElement);
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
            if (cerrando || !tieneAutocierre) return;
            pausar();
            if (estaPausado()) return;
            if (restante <= 0) {
                cerrar();
                return;
            }
            iniciadoEn = performance.now();
            temporizador = window.setTimeout(vencer, restante);
        }

        if (boton) {
            boton.hidden = false;
            boton.addEventListener("click", cerrar);
        }
        if (tieneAutocierre) {
            mensaje.addEventListener("mouseenter", actualizar);
            mensaje.addEventListener("mouseleave", actualizar);
            mensaje.addEventListener("focusin", actualizar);
            mensaje.addEventListener("focusout", function () {
                // Esperar a que el navegador termine de mover el foco.
                window.setTimeout(actualizar, 0);
            });
            document.addEventListener("visibilitychange", actualizar);
            actualizar();
        }
    });
});
