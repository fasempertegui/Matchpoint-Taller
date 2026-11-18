(function () {
    var tooltip = document.createElement("div");
    tooltip.className = "estado-tooltip";
    tooltip.id = "estado-tooltip-compartido";
    tooltip.setAttribute("role", "tooltip");
    tooltip.hidden = true;
    document.body.append(tooltip);
    var actual = null;
    var temporizador;

    function cerrar() {
        window.clearTimeout(temporizador);
        if (actual) actual.removeAttribute("aria-describedby");
        actual = null;
        tooltip.hidden = true;
        if (tooltip.parentElement !== document.body) document.body.append(tooltip);
    }
    function posicionar() {
        if (!actual || !actual.getClientRects().length) { cerrar(); return; }
        var caja = actual.getBoundingClientRect();
        var ancho = tooltip.offsetWidth;
        var alto = tooltip.offsetHeight;
        tooltip.style.left = Math.max(8, Math.min(caja.left, window.innerWidth - ancho - 8)) + "px";
        var debajo = caja.bottom + 6;
        tooltip.style.top = Math.max(8, debajo + alto <= window.innerHeight - 8 ? debajo : caja.top - alto - 6) + "px";
    }
    function abrir(indicador) {
        window.clearTimeout(temporizador);
        if (actual !== indicador) cerrar();
        actual = indicador;
        var contenedor = indicador.closest("dialog[open]") || document.body;
        if (tooltip.parentElement !== contenedor) contenedor.append(tooltip);
        tooltip.textContent = indicador.dataset.estadoTooltip;
        indicador.setAttribute("aria-describedby", tooltip.id);
        tooltip.hidden = false;
        posicionar();
    }
    function salida(evento) {
        if (!actual) return;
        var destino = evento.relatedTarget;
        if (destino && (actual.contains(destino) || tooltip.contains(destino))) return;
        var enfocado = document.activeElement;
        if (evento.type === "pointerout" && (actual === enfocado
            || (enfocado.matches("button, a") && enfocado.contains(actual)))) return;
        window.clearTimeout(temporizador);
        temporizador = window.setTimeout(cerrar, 180);
    }
    document.addEventListener("pointerover", function (evento) {
        var indicador = evento.target.closest("[data-estado-tooltip]");
        if (indicador) abrir(indicador);
        else if (tooltip.contains(evento.target)) window.clearTimeout(temporizador);
    });
    document.addEventListener("pointerout", function (evento) {
        if (evento.target.closest("[data-estado-tooltip]") || tooltip.contains(evento.target)) salida(evento);
    });
    document.addEventListener("focusin", function (evento) {
        var indicador = evento.target.closest("[data-estado-tooltip]");
        if (!indicador) indicador = evento.target.querySelector("[data-estado-tooltip]");
        if (indicador) abrir(indicador);
        else cerrar();
    });
    document.addEventListener("focusout", salida);
    document.addEventListener("click", function (evento) {
        var indicador = evento.target.closest("[data-estado-tooltip]");
        if (indicador) abrir(indicador);
        else if (!tooltip.contains(evento.target)) cerrar();
    });
    document.addEventListener("keydown", function (evento) { if (evento.key === "Escape") cerrar(); });
    document.addEventListener("close", function (evento) {
        if (tooltip.parentElement === evento.target) cerrar();
    }, true);
    window.addEventListener("resize", cerrar);
    document.addEventListener("scroll", cerrar, true);
}());
