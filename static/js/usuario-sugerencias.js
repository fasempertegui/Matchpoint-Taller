document.addEventListener("DOMContentLoaded", function () {
    var formulario = document.querySelector("[data-nombre-usuario-url]");
    if (!formulario) return;

    var nombre = formulario.querySelector("[name='nombre']");
    var apellido = formulario.querySelector("[name='apellido']");
    var nombreUsuario = formulario.querySelector("[name='nombre_usuario']");
    var errorNombreUsuario = formulario.querySelector("[data-error-nombre-usuario]");
    var ultimaSolicitud = 0;

    function normalizar(texto) {
        return texto.normalize("NFKD").replace(/[^\x00-\x7F]/g, "").toLowerCase().replace(/[^a-z]/g, "");
    }

    function actualizarNombreUsuario() {
        var solicitud = ++ultimaSolicitud;
        var base = normalizar(apellido.value);
        var inicial = normalizar(nombre.value).charAt(0);
        errorNombreUsuario.hidden = true;
        nombreUsuario.value = base && inicial ? base + inicial : "";
        if (/\p{Number}/u.test(nombre.value + apellido.value)) {
            nombreUsuario.value = "";
            return;
        }
        if (!nombreUsuario.value) return;

        var url = new URL(formulario.dataset.nombreUsuarioUrl, window.location.origin);
        url.searchParams.set("nombre", nombre.value.trim());
        url.searchParams.set("apellido", apellido.value.trim());

        fetch(url, {headers: {Accept: "application/json"}, cache: "no-store"})
            .then(function (respuesta) {
                return respuesta.json().then(function (datos) {
                    if (!respuesta.ok) throw new Error(datos.error || "No se pudo generar el usuario.");
                    return datos;
                });
            })
            .then(function (datos) {
                if (solicitud === ultimaSolicitud) nombreUsuario.value = datos.nombre_usuario;
            })
            .catch(function (excepcion) {
                if (solicitud !== ultimaSolicitud) return;
                nombreUsuario.value = "";
                errorNombreUsuario.textContent = excepcion.message;
                errorNombreUsuario.hidden = false;
            });
    }

    nombre.addEventListener("input", actualizarNombreUsuario);
    apellido.addEventListener("input", actualizarNombreUsuario);
    actualizarNombreUsuario();

    var botonContrasena = formulario.querySelector("[data-sugerir-contrasena]");
    if (!botonContrasena) return;

    var contrasena = formulario.querySelector("[name='contrasena']");
    var errorContrasena = formulario.querySelector("[data-error-contrasena]");
    botonContrasena.addEventListener("click", function () {
        botonContrasena.disabled = true;
        errorContrasena.hidden = true;

        fetch(botonContrasena.dataset.url, {headers: {Accept: "application/json"}, cache: "no-store"})
            .then(function (respuesta) {
                return respuesta.json().then(function (datos) {
                    if (!respuesta.ok) throw new Error(datos.error || "No se pudo generar la contraseña.");
                    return datos;
                });
            })
            .then(function (datos) {
                contrasena.value = datos.contrasena;
            })
            .catch(function (excepcion) {
                errorContrasena.textContent = excepcion.message;
                errorContrasena.hidden = false;
            })
            .finally(function () {
                botonContrasena.disabled = false;
            });
    });
});
