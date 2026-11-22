document.addEventListener("input", function (evento) {
    var campo = evento.target;
    if (!campo.matches("[data-paginacion-numero]")) return;
    campo.setCustomValidity(/^[0-9]*$/.test(campo.value) ? "" : "Ingresá un número entero de página.");
});
