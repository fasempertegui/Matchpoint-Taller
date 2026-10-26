document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-observaciones]").forEach(function (bloque) {
        var agregar = bloque.querySelector("[data-agregar-observaciones]");
        var contenedor = bloque.querySelector("[data-campo-observaciones]");
        var campo = contenedor.querySelector("textarea");
        function ajustar() {
            if (contenedor.hidden) return;
            var estilo = window.getComputedStyle(campo);
            var linea = parseFloat(estilo.lineHeight);
            var relleno = parseFloat(estilo.paddingTop) + parseFloat(estilo.paddingBottom);
            var borde = parseFloat(estilo.borderTopWidth) + parseFloat(estilo.borderBottomWidth);
            campo.style.height = "auto";
            var altura = campo.scrollHeight + borde;
            var maximo = linea * 6 + relleno + borde;
            campo.style.height = Math.min(maximo, Math.max(linea * 3 + relleno + borde, altura)) + "px";
            campo.style.overflowY = altura > maximo ? "auto" : "hidden";
        }
        function mostrar(abierto) {
            agregar.hidden = abierto;
            agregar.setAttribute("aria-expanded", String(abierto));
            contenedor.hidden = !abierto;
            ajustar();
        }
        agregar.addEventListener("click", function () { mostrar(true); campo.focus(); });
        campo.addEventListener("input", ajustar);
        campo.addEventListener("blur", function () {
            if (!campo.value.trim()) { campo.value = ""; mostrar(false); }
        });
        bloque.addEventListener("observaciones:actualizar", function () { mostrar(Boolean(campo.value.trim())); });
        window.addEventListener("resize", ajustar);
        ajustar();
    });
});
