document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-pestanas]").forEach(function (contenedor) {
        var botones = contenedor.querySelectorAll(".pestana-boton");
        var paneles = contenedor.querySelectorAll(".pestana-panel");
        if (!botones.length) return;

        function activar(nombre) {
            botones.forEach(function (boton) {
                boton.setAttribute("aria-selected", boton.dataset.pestana === nombre ? "true" : "false");
            });
            paneles.forEach(function (panel) {
                panel.hidden = panel.dataset.panel !== nombre;
            });
        }

        botones.forEach(function (boton) {
            boton.addEventListener("click", function () {
                activar(boton.dataset.pestana);
                history.replaceState(null, "", "#" + boton.dataset.pestana);
            });
        });

        var inicial = location.hash ? location.hash.slice(1) : null;
        var existeInicial = inicial && contenedor.querySelector('.pestana-boton[data-pestana="' + inicial + '"]');
        activar(existeInicial ? inicial : botones[0].dataset.pestana);
    });
});
