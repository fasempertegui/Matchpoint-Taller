document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-historial-asignaciones]").forEach(function (boton) {
        var modal = document.getElementById(boton.getAttribute("aria-controls"));
        boton.addEventListener("click", function () {
            document.documentElement.classList.add("modal-abierto");
            modal.showModal();
        });
        modal.addEventListener("close", function () {
            if (!document.querySelector("dialog[open]")) document.documentElement.classList.remove("modal-abierto");
        });
    });
});
