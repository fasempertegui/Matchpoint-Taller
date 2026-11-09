document.addEventListener("DOMContentLoaded", function () {
    var formulario = document.querySelector("[data-cambio-contrasena]");
    if (!formulario) return;

    formulario.querySelectorAll("[data-mostrar-contrasena]").forEach(function (boton) {
        var campo = document.getElementById(boton.getAttribute("aria-controls"));
        var etiqueta = formulario.querySelector("label[for='" + campo.id + "']").textContent.toLowerCase();
        var iconoMostrar = boton.querySelector("[data-icono-mostrar]");
        var iconoOcultar = boton.querySelector("[data-icono-ocultar]");
        boton.hidden = false;

        boton.addEventListener("click", function () {
            var mostrar = campo.type === "password";
            campo.type = mostrar ? "text" : "password";
            boton.setAttribute("aria-label", (mostrar ? "Ocultar " : "Mostrar ") + etiqueta);
            iconoMostrar.hidden = mostrar;
            iconoOcultar.hidden = !mostrar;
        });
    });

    var nuevaContrasena = formulario.querySelector("[name='new_password1']");
    var confirmacionContrasena = formulario.querySelector("[name='new_password2']");
    var guardar = formulario.querySelector("button[type='submit']");
    var reglas = document.querySelectorAll("[data-regla-contrasena]");

    function actualizarReglas() {
        var valor = nuevaContrasena.value;
        var condiciones = {
            longitud: Array.from(valor).length >= 8,
            numeros: valor.length > 0 && !/^\p{Decimal_Number}+$/u.test(valor),
            coincidencia: valor.length > 0 && valor === confirmacionContrasena.value
        };
        guardar.disabled = !Object.values(condiciones).every(function (cumple) { return cumple; });
        reglas.forEach(function (regla) {
            var cumple = condiciones[regla.dataset.reglaContrasena];
            regla.dataset.cumple = String(cumple);
            regla.querySelector(".contrasena-regla-estado").hidden = false;
            regla.querySelector("[data-regla-check]").hidden = !cumple;
            regla.querySelector("[data-regla-cruz]").hidden = cumple;
            regla.querySelector("[data-regla-resultado]").textContent = cumple ? "Cumple: " : "No cumple: ";
        });
    }

    formulario.addEventListener("submit", function (evento) {
        actualizarReglas();
        if (guardar.disabled) evento.preventDefault();
    });

    nuevaContrasena.addEventListener("input", actualizarReglas);
    nuevaContrasena.addEventListener("change", actualizarReglas);
    confirmacionContrasena.addEventListener("input", actualizarReglas);
    confirmacionContrasena.addEventListener("change", actualizarReglas);
    actualizarReglas();
});
