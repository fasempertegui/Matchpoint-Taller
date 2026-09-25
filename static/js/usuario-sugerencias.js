document.addEventListener("DOMContentLoaded", function () {
    var botonUsuario = document.querySelector("[data-sugerir-usuario]");
    if (!botonUsuario) return;

    var formulario = botonUsuario.closest("form");
    var botonContrasena = formulario.querySelector("[data-sugerir-contrasena]");
    var nombre = formulario.querySelector("[name='nombre']");
    var apellido = formulario.querySelector("[name='apellido']");
    var nombreUsuario = formulario.querySelector("[name='nombre_usuario']");
    var contrasena = formulario.querySelector("[name='contrasena']");
    var errorUsuario = formulario.querySelector("[data-error-usuario]");
    var errorContrasena = formulario.querySelector("[data-error-contrasena]");

    function sugerir(boton, url, campo, error, propiedad) {
        boton.disabled = true;
        error.hidden = true;

        fetch(url, {headers: {Accept: "application/json"}, cache: "no-store"})
            .then(function (respuesta) {
                return respuesta.json().then(function (datos) {
                    if (!respuesta.ok) throw new Error(datos.error || "No se pudo generar la sugerencia.");
                    return datos;
                });
            })
            .then(function (datos) {
                campo.value = datos[propiedad];
            })
            .catch(function (excepcion) {
                error.textContent = excepcion.message;
                error.hidden = false;
            })
            .finally(function () {
                boton.disabled = false;
            });
    }

    botonUsuario.addEventListener("click", function () {
        if (!nombre.value.trim()) {
            nombre.reportValidity();
            nombre.focus();
            return;
        }
        if (!apellido.value.trim()) {
            apellido.reportValidity();
            apellido.focus();
            return;
        }

        var url = new URL(botonUsuario.dataset.url, window.location.origin);
        url.searchParams.set("nombre", nombre.value.trim());
        url.searchParams.set("apellido", apellido.value.trim());
        sugerir(botonUsuario, url, nombreUsuario, errorUsuario, "nombre_usuario");
    });

    botonContrasena.addEventListener("click", function () {
        sugerir(
            botonContrasena,
            botonContrasena.dataset.url,
            contrasena,
            errorContrasena,
            "contrasena"
        );
    });
});
