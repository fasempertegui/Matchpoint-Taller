(function () {
    "use strict";
    var formulario = document.querySelector("[data-ingreso-formulario]");
    if (!formulario) return;
    var medio = formulario.querySelector("[data-ingreso-medio]");
    function actualizarMedio() {
        var requiereReferencia = ["transferencia", "tarjeta", "qr"].includes(medio.value);
        formulario.querySelectorAll("[data-ingreso-no-efectivo]").forEach(function (grupo) {
            grupo.hidden = !requiereReferencia;
            grupo.querySelectorAll("input").forEach(function (campo) {
                campo.required = requiereReferencia;
            });
        });
    }
    var categoria = formulario.querySelector("[data-categoria-egreso]");
    function actualizarCategoria() {
        formulario.querySelectorAll("[data-devolucion-vinculo]").forEach(function (bloque) {
            bloque.hidden = categoria.value !== "devoluciones";
        });
    }
    if (categoria) {
        categoria.addEventListener("change", actualizarCategoria);
        actualizarCategoria();
    }
    medio.addEventListener("change", actualizarMedio);
    actualizarMedio();
})();
