document.addEventListener("DOMContentLoaded", function () {
    var dialogo = document.getElementById("agenda-selector-fecha");
    if (!dialogo || !window.flatpickr) return;

    var cerrar = dialogo.querySelector("button[type=submit]");
    var disparador;
    var destino;
    var calendario = window.flatpickr(dialogo.querySelector("[data-agenda-calendario-campo]"), {
        inline: true,
        disableMobile: true,
        clickOpens: false,
        closeOnSelect: false,
        dateFormat: "Y-m-d",
        ariaDateFormat: "l j F Y",
        locale: { ...window.flatpickr.l10ns.es, monthAriaLabel: "Mes", yearAriaLabel: "Año" },
        now: dialogo.dataset.hoy,
        minDate: dialogo.dataset.fechaMinima,
        maxDate: dialogo.dataset.fechaMaxima,
        onChange: function (_fechas, fecha) {
            dialogo.close();
            if (fecha === destino.searchParams.get("fecha")) return;
            destino.searchParams.set("fecha", fecha);
            window.location.assign(destino);
        },
    });

    document.addEventListener("click", function (evento) {
        var boton = evento.target.closest("[data-agenda-elegir-fecha]");
        if (!boton) return;

        disparador = boton;
        destino = new URL(boton.dataset.agendaElegirFecha, window.location.href);
        calendario.setDate(destino.searchParams.get("fecha"));
        dialogo.showModal();
        document.documentElement.classList.add("modal-abierto");
        calendario.calendarContainer.querySelector(".flatpickr-day.selected")?.focus();
    });

    // El calendario en línea no usa el campo de texto al que Flatpickr devuelve el foco.
    dialogo.addEventListener("keydown", function (evento) {
        if (!evento.target.matches(".flatpickr-day")) return;
        if (evento.key === "Escape" || (evento.key === "Tab" && evento.shiftKey)) {
            evento.preventDefault();
            evento.stopPropagation();
            if (evento.key === "Escape") dialogo.close();
            else cerrar.focus();
        }
    }, true);

    dialogo.addEventListener("close", function () {
        document.documentElement.classList.remove("modal-abierto");
        disparador?.focus({preventScroll: true});
    });
});
