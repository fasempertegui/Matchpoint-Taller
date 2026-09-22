document.addEventListener("DOMContentLoaded", function () {
    var boton = document.querySelector("[data-sugerir-credenciales]");
    if (!boton) return;

    var formulario = boton.closest("form");
    var nombre = formulario.querySelector("[name='nombre']");
    var apellido = formulario.querySelector("[name='apellido']");
    var nombreUsuario = formulario.querySelector("[name='nombre_usuario']");
    var contrasena = formulario.querySelector("[name='contrasena']");
    var error = formulario.querySelector("[data-error-sugerencias]");
    var textoOriginal = boton.textContent.trim();

    boton.addEventListener("click", function () {
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

        var url = new URL(boton.dataset.url, window.location.origin);
        url.searchParams.set("nombre", nombre.value.trim());
        url.searchParams.set("apellido", apellido.value.trim());

        boton.disabled = true;
        boton.textContent = "Generando...";
        error.hidden = true;

        fetch(url, {headers: {Accept: "application/json"}})
            .then(function (respuesta) {
                return respuesta.json().then(function (datos) {
                    if (!respuesta.ok) throw new Error(datos.error || "No se pudieron generar las credenciales.");
                    return datos;
                });
            })
            .then(function (datos) {
                nombreUsuario.value = datos.nombre_usuario;
                contrasena.value = datos.contrasena;
            })
            .catch(function (excepcion) {
                error.textContent = excepcion.message;
                error.hidden = false;
            })
            .finally(function () {
                boton.disabled = false;
                boton.textContent = textoOriginal;
            });
    });
});
