document.addEventListener("DOMContentLoaded", function () {
    var modal = document.querySelector("[data-oferta-descripcion-modal]");
    if (!modal) return;
    var origen = null;
    var cerrar = modal.querySelector("[data-oferta-descripcion-cerrar]");

    document.addEventListener("click", function (evento) {
        var boton = evento.target.closest("[data-oferta-descripcion]");
        if (!boton || evento.defaultPrevented) return;
        var tarjeta = boton.closest(".oferta-producto");
        var descripcion = tarjeta.querySelector(".oferta-producto-descripcion");
        if (!descripcion) return;
        origen = boton;
        modal.querySelector("[data-oferta-descripcion-titulo]").textContent = tarjeta.querySelector("h2").textContent;
        modal.querySelector("[data-oferta-descripcion-texto]").textContent = descripcion.textContent;
        document.documentElement.classList.add("modal-abierto");
        modal.showModal();
        cerrar.focus({preventScroll: true});
    });

    cerrar.addEventListener("click", function () { modal.close(); });
    modal.addEventListener("click", function (evento) {
        var rect = modal.getBoundingClientRect();
        if (evento.target === modal && (
            evento.clientX < rect.left || evento.clientX > rect.right
            || evento.clientY < rect.top || evento.clientY > rect.bottom
        )) modal.close();
    });
    modal.addEventListener("close", function () {
        document.documentElement.classList.remove("modal-abierto");
        if (origen) origen.focus({preventScroll: true});
        origen = null;
    });
});
