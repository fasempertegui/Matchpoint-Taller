document.addEventListener("DOMContentLoaded", function () {
    var boton = document.querySelector("[data-cambiar-periodo]");
    if (!boton) return;
    var formulario = document.getElementById(boton.getAttribute("aria-controls"));
    boton.addEventListener("click", function () {
        formulario.hidden = !formulario.hidden;
        boton.setAttribute("aria-expanded", String(!formulario.hidden));
        if (!formulario.hidden) formulario.elements.fecha_desde.focus();
    });
});
