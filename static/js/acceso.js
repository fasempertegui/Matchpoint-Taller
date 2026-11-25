document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-toggle-password]").forEach(function (boton) {
        var campo = document.getElementById(boton.getAttribute("aria-controls"));
        if (!campo) return;
        var etiqueta = boton.dataset.etiqueta || "contraseña";
        var iconoMostrar = boton.querySelector("[data-icono-mostrar]");
        var iconoOcultar = boton.querySelector("[data-icono-ocultar]");

        boton.addEventListener("click", function () {
            var mostrar = campo.type === "password";
            campo.type = mostrar ? "text" : "password";
            boton.setAttribute("aria-label", (mostrar ? "Ocultar " : "Mostrar ") + etiqueta);
            boton.setAttribute("aria-pressed", String(mostrar));
            if (iconoMostrar) iconoMostrar.hidden = mostrar;
            if (iconoOcultar) iconoOcultar.hidden = !mostrar;
        });
    });
});
