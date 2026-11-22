document.addEventListener("click", function (evento) {
    var boton = evento.target.closest("[data-entrega]");
    if (!boton) return;

    var panel = document.getElementById(boton.getAttribute("aria-controls"));
    var abrir = boton.getAttribute("aria-expanded") !== "true";
    panel.hidden = !abrir;
    boton.setAttribute("aria-expanded", String(abrir));
    boton.textContent = abrir ? "Ocultar entrega" : "Ver entrega";
});
