document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-pestanas]").forEach(function (contenedor) {
        var botones = contenedor.querySelectorAll(".pestana-boton");
        var paneles = contenedor.querySelectorAll(".pestana-panel");
        if (!botones.length) return;

        function activar(nombre) {
            botones.forEach(function (boton) {
                var seleccionado = boton.dataset.pestana === nombre;
                boton.setAttribute("aria-selected", seleccionado ? "true" : "false");
                boton.tabIndex = seleccionado ? 0 : -1;
            });
            paneles.forEach(function (panel) {
                panel.hidden = panel.dataset.panel !== nombre;
            });
        }

        botones.forEach(function (boton, indice) {
            boton.addEventListener("click", function () {
                activar(boton.dataset.pestana);
                history.replaceState(null, "", "#" + boton.dataset.pestana);
            });
            boton.addEventListener("keydown", function (evento) {
                var siguiente;
                if (evento.key === "ArrowRight") siguiente = (indice + 1) % botones.length;
                else if (evento.key === "ArrowLeft") siguiente = (indice + botones.length - 1) % botones.length;
                else if (evento.key === "Home") siguiente = 0;
                else if (evento.key === "End") siguiente = botones.length - 1;
                else return;

                evento.preventDefault();
                botones[siguiente].focus();
                botones[siguiente].click();
            });
        });

        var inicial = location.hash ? location.hash.slice(1) : null;
        var existeInicial = Array.from(botones).some(function (boton) {
            return boton.dataset.pestana === inicial;
        });
        activar(existeInicial ? inicial : botones[0].dataset.pestana);
    });
});
