document.addEventListener("DOMContentLoaded", function () {
    var datos = document.querySelector("[data-reserva-datos]");
    if (!datos) return;
    var sede = datos.elements.namedItem("sede");
    var fecha = datos.elements.namedItem("fecha");
    var canchas = Array.from(datos.querySelectorAll("[name='cancha']"));
    var seleccion = document.querySelector("[data-reserva-seleccion]");
    var avisoCanchas = datos.querySelector("[data-aviso-canchas]");

    function actualizarCanchas() {
        var disponibles = 0;
        canchas.forEach(function (cancha) {
            var visible = cancha.dataset.sede === sede.value;
            cancha.closest("label").hidden = !visible;
            cancha.disabled = !visible;
            if (!visible) cancha.checked = false;
            if (visible) disponibles++;
        });
        avisoCanchas.hidden = disponibles > 0;
        avisoCanchas.textContent = sede.value ? "No hay canchas activas en esta sede." : "Elegí una sede.";
    }
    function ocultarTurnos() {
        if (seleccion) seleccion.hidden = true;
    }
    sede.addEventListener("change", actualizarCanchas);
    datos.addEventListener("change", ocultarTurnos);
    fecha.addEventListener("change", ocultarTurnos);
    actualizarCanchas();

    var calendario = document.querySelector("[data-calendario]");
    var dias = calendario.querySelector("[data-dias-calendario]");
    var tituloMes = calendario.querySelector("[data-mes-actual]");
    var anterior = calendario.querySelector("[data-mes-anterior]");
    var siguiente = calendario.querySelector("[data-mes-siguiente]");
    var fechaElegida = new Date((fecha.value || fecha.min) + "T00:00:00");
    var mes = new Date(fechaElegida.getFullYear(), fechaElegida.getMonth(), 1);
    var primerDia = new Date(fecha.min + "T00:00:00");
    var ultimoDia = new Date(fecha.max + "T00:00:00");
    var primerMes = new Date(primerDia.getFullYear(), primerDia.getMonth(), 1);
    var ultimoMes = new Date(ultimoDia.getFullYear(), ultimoDia.getMonth(), 1);
    if (mes < primerMes || mes > ultimoMes) mes = new Date(primerMes);
    var formatoMes = new Intl.DateTimeFormat("es-AR", {month: "long", year: "numeric"});
    var formatoDia = new Intl.DateTimeFormat("es-AR", {weekday: "long", day: "numeric", month: "long", year: "numeric"});

    function mostrarMes() {
        tituloMes.textContent = formatoMes.format(mes);
        anterior.disabled = mes <= primerMes;
        siguiente.disabled = mes >= ultimoMes;
        dias.replaceChildren();
        var espacios = (mes.getDay() + 6) % 7;
        for (var espacio = 0; espacio < espacios; espacio++) dias.appendChild(document.createElement("span"));
        var cantidadDias = new Date(mes.getFullYear(), mes.getMonth() + 1, 0).getDate();
        for (var numero = 1; numero <= cantidadDias; numero++) {
            var dia = new Date(mes.getFullYear(), mes.getMonth(), numero);
            var valor = dia.getFullYear() + "-" + String(dia.getMonth() + 1).padStart(2, "0") + "-" + String(numero).padStart(2, "0");
            var botonDia = document.createElement("button");
            botonDia.type = "button";
            botonDia.className = "reserva-dia";
            botonDia.textContent = numero;
            botonDia.dataset.fecha = valor;
            botonDia.disabled = valor < fecha.min || valor > fecha.max;
            botonDia.setAttribute("aria-label", formatoDia.format(dia));
            botonDia.setAttribute("aria-pressed", String(valor === fecha.value));
            dias.appendChild(botonDia);
        }
    }
    dias.addEventListener("click", function (evento) {
        var botonDia = evento.target.closest("[data-fecha]");
        if (!botonDia || botonDia.disabled) return;
        fecha.value = botonDia.dataset.fecha;
        fecha.dispatchEvent(new Event("change", {bubbles: true}));
        mostrarMes();
    });
    anterior.addEventListener("click", function () {
        mes = new Date(mes.getFullYear(), mes.getMonth() - 1, 1);
        mostrarMes();
    });
    siguiente.addEventListener("click", function () {
        mes = new Date(mes.getFullYear(), mes.getMonth() + 1, 1);
        mostrarMes();
    });
    mostrarMes();
    fecha.hidden = true;
    calendario.hidden = false;

    var formulario = document.querySelector("[data-reserva-turnos]");
    var boton = formulario && formulario.querySelector("[data-registrar-reserva]");
    if (!boton) return;
    var total = formulario.querySelector("[data-reserva-total]");
    var error = formulario.querySelector("[data-error-seleccion]");
    var precio = Number(formulario.dataset.precioCentavos);
    var moneda = new Intl.NumberFormat("es-AR", {style: "currency", currency: "ARS"});

    function actualizarSeleccion() {
        var turnos = Array.from(formulario.querySelectorAll("[name='turnos']:checked"));
        var consecutivos = turnos.every(function (turno, indice) {
            return indice === 0 || (
                turnos[indice - 1].dataset.fin === turno.dataset.inicio &&
                turnos[indice - 1].dataset.franja === turno.dataset.franja
            );
        });
        var importe = moneda.format(precio * turnos.length / 100);
        total.textContent = turnos.length + (turnos.length === 1 ? " turno" : " turnos") + " · Total: " + importe;
        error.hidden = consecutivos;
        error.textContent = "Seleccioná turnos consecutivos dentro de una misma franja de funcionamiento.";
        boton.disabled = !turnos.length || !consecutivos;
        var horarios = turnos.map(function (turno) {
            return turno.dataset.inicio.padStart(2, "0") + ":00 a " + turno.dataset.fin.padStart(2, "0") + ":00";
        }).join("\n");
        formulario.dataset.confirmar = "¿Confirmar esta reserva?\n\nOrganizador: " + formulario.dataset.organizador +
            "\nCancha: " + formulario.dataset.cancha + "\nFecha: " + formulario.dataset.fecha +
            "\n\n" + horarios + "\n\nTotal: " + importe;
    }
    formulario.addEventListener("change", actualizarSeleccion);
    actualizarSeleccion();
});
