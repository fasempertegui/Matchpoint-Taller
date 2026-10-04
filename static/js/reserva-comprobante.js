document.addEventListener("DOMContentLoaded", () => {
    const boton = document.querySelector("[data-imprimir-comprobante]");
    if (boton) {
        boton.addEventListener("click", () => window.print());
    }
});
