import type { en } from "./en";

// Spanish copy. Same figures as en.ts; written in Spanish, not translated line by line (the design notes).

export const es: typeof en = {
  langName: "Español",
  meta: {
    title: "Caseback",
    description:
      "Un sensor bajo el reloj que ya llevas, con su diseño y su código publicados. Un disco fino en la tapa mide pulso, sueño y movimiento para una app de iPhone. Es un prototipo en fase temprana.",
  },
  nav: {
    home: "Caseback",
    back: "Volver a la tapa",
    github: "GitHub",
    waitlist: "Lista de espera",
    language: "Idioma",
    skip: "Saltar la entrada",
    plate: "Lámina",
    of: "de",
    sections: "Secciones",
  },
  home: {
    lead: "Un sensor bajo el reloj que ya llevas.",
    sub: "Un disco de 25 mm se pega a la tapa de tu reloj y mide el pulso, el sueño y el movimiento.",
    side: {
      title: "De lado, en la muñeca",
      watch: "Tu reloj",
      disc: "Caseback",
      wrist: "Muñeca",
      label: "Vista lateral: el disco se pega a la tapa del reloj y queda entre el reloj y la muñeca.",
    },
    status: "Fase de prototipo",
    drawing:
      "Dibujo de un reloj que se da la vuelta y se convierte en el disco, en 3D: sus piezas bajan una a una dentro de la carcasa y el disco cerrado se gira hacia la cara de la piel. De partes del disco salen líneas hacia las secciones de esta web.",
    callouts: {
      wear: { label: "Cómo se lleva", part: "Almohadilla de microsucción" },
      measure: { label: "Qué mide", part: "Ventana del sensor" },
      app: { label: "La app", part: "Antena Bluetooth" },
      open: { label: "Código y licencias", part: "Junta entre carcasa y tapa" },
    },
  },
  wear: {
    title: "Cómo se lleva",
    plates: [
      {
        title: "Debajo de la tapa",
        body: [
          "El disco va en la tapa trasera del reloj, entre el reloj y la muñeca. Toda la cara que toca la tapa es una almohadilla de microsucción: está pensado para sujetarse sin pegamento y sin imanes cerca del movimiento, y para quitarse y volver a ponerse.",
          "Está diseñado con 25 mm de diámetro y 3,1 mm de grosor, y el borde del lado de la piel redondeado. Por fuera, el reloj se ve igual.",
        ],
        art: {
          label: "Dibujo de la parte de atrás de un reloj. El disco, en 3D, sube hasta la tapa y se queda en ella.",
          caption: "El disco es el modelo 3D del diseño actual; el reloj está dibujado.",
          labels: [
            { key: "caseback", name: "Tapa del reloj" },
            { key: "pad", name: "Almohadilla de microsucción", value: "Ø 23 mm" },
            { key: "disc", name: "Disco", value: "Ø 25 mm" },
            { key: "thick", name: "Grosor", value: "3,1 mm" },
          ],
        },
      },
      {
        title: "Se carga en el reloj",
        body: [
          "Para cargarlo no hace falta quitarlo: el reloj se deja con la esfera hacia arriba sobre la base de carga y el disco encaja en ella. Un gancho y un pestillo con muelle entran en dos huecos del borde del disco y lo aprietan contra dos pines con muelle, que tocan los dos contactos de acero de la cara de la piel.",
          "Para sacarlo se pulsa el botón del borde de la base. La base se conecta por USB-C y no lleva imanes. El mismo encaje vale con el disco solo o en la banda.",
        ],
        art: {
          label: "Dibujo de un reloj con la esfera hacia arriba que baja sobre la base de carga, también dibujada, hasta que el disco de su tapa, en 3D, encaja en ella.",
          caption: "El disco es el modelo 3D del diseño actual; el reloj y la base están dibujados.",
          labels: [
            { key: "watch", name: "Reloj, esfera arriba" },
            { key: "disc", name: "Disco, encajado" },
            { key: "button", name: "Botón para soltarlo" },
            { key: "charger", name: "Base de carga", value: "Ø 34 mm" },
          ],
        },
      },
      {
        title: "Sin reloj, en la banda",
        body: [
          "Para dormir o entrenar sin reloj, el disco entra en una banda: una correa tejida que sale de un soporte de silicona, da una vuelta a la muñeca, pasa por una hebilla de acero y se cierra sobre sí misma con un cierre de gancho y lazo.",
          "El disco entra en el soporte por el lado de la piel y su cara queda fuera, así que se carga sin sacarlo de la banda: la base encaja igual.",
        ],
        art: {
          label: "Dibujo de la banda de pie. El disco, en 3D, entra en el soporte desde dentro del aro.",
          caption: "El disco es el modelo 3D del diseño actual; la banda está dibujada.",
          labels: [
            { key: "buckle", name: "Hebilla de acero" },
            { key: "holder", name: "Soporte de silicona" },
            { key: "strap", name: "Correa tejida", value: "27,4 mm" },
            { key: "hook", name: "Cierre de gancho y lazo" },
          ],
        },
      },
    ],
  },
  measure: {
    title: "Qué mide",
    plates: [
      {
        title: "Qué siente el disco",
        body: [
          "Tres LED pequeños, verde, rojo e infrarrojo, iluminan la piel bajo el disco, y un fotodiodo al lado mide cuánta de esa luz vuelve. La sangre absorbe luz y la cantidad de sangre bajo el sensor cambia un poco con cada latido, así que la luz que vuelve baja y se recupera al ritmo del pulso.",
          "Un acelerómetro mide el movimiento. De él salen los pasos y las fases del sueño, y le dice al algoritmo del pulso qué parte de la señal es movimiento del brazo. Un termistor en la cara que toca la piel lee la temperatura de la piel.",
          "No hay ECG. Un ECG necesita dos contactos en partes distintas del cuerpo, y un disco bajo el reloj toca una sola muñeca.",
        ],
      },
      {
        title: "Tres respuestas y de dónde salen",
        body: [
          "La app abre con tres respuestas: Recuperación y Sueño, las dos de 0 a 100, y Movimiento, tus pasos frente a un día normal tuyo.",
          "Cada una se calcula con señales que registra el disco. Recuperación compara con tus últimas semanas el pulso en reposo, la variabilidad (HRV), el sueño de anoche y la temperatura de la piel. Sueño sale del movimiento y del pulso, y Movimiento del movimiento. El oxígeno en sangre se muestra aparte, como tendencia.",
          "Una marca llena se muestra como un valor y una marca abierta como una tendencia. Caseback no es un producto sanitario y no diagnostica nada.",
        ],
      },
    ],
    art: {
      sense: {
        disc: "Disco",
        skin: "Piel",
        leds: "LED",
        pd: "Fotodiodo",
        green: "Luz verde",
        red: "Luz roja",
        ir: "Luz infrarroja",
        ppgTitle: "Lo que lee el fotodiodo",
        seconds: "s",
        label:
          "El disco sobre la piel. La luz verde, roja e infrarroja de tres LED atraviesa la piel y vuelve a un fotodiodo. Debajo, ocho segundos de una forma de onda de pulso grabada.",
        note: "Esquema. Las distancias y las profundidades no están a escala; las longitudes de onda largas llegan más hondo.",
        source: "La forma de onda es una grabación en un dedo, de un monitor de hospital (BIDMC, sujeto 36, datos públicos). No es del disco.",
      },
      signals: {
        recovery: "Recuperación",
        recoverySub: "0 a 100",
        sleep: "Sueño",
        sleepSub: "0 a 100",
        movement: "Movimiento",
        movementSub: "pasos frente a tu día normal",
        hr: "Pulso",
        hrv: "HRV",
        temp: "Temperatura de la piel",
        spo2: "Oxígeno en sangre",
        motion: "Movimiento",
        label:
          "Las tres respuestas de la app, Recuperación, Sueño y Movimiento, unidas con líneas a las señales con las que se calculan. El pulso, la HRV, el sueño y los pasos son marcas llenas; la temperatura de la piel y el oxígeno en sangre son marcas abiertas: la app las muestra como tendencias.",
        headAnswers: "Respuestas",
        headSignals: "Señales",
        legendFilled: "Marca llena: se muestra como un valor",
        legendOpen: "Marca abierta: se muestra como tendencia",
      },
    },
  },
  app: {
    title: "La app",
    plates: [
      {
        title: "Hoy",
        body: [
          "La primera pantalla responde a cómo has dormido y cuánto te has recuperado. Primero va la puntuación, después una frase y debajo la gráfica de la que sale.",
          "La app es para iPhone; Android vendrá después.",
        ],
      },
      {
        title: "Tendencias",
        body: [
          "Tendencias compara los últimos 7, 30 o 90 días con lo que es normal en ti. La línea de puntos es tu mediana y la franja tenue detrás de la línea es tu rango habitual. Mantén el dedo sobre la gráfica para leer cualquier día.",
          "Cada puntuación y cada medida abre su propia pantalla, con una frase sobre lo que suele afectarla.",
        ],
      },
      {
        title: "Tus datos se quedan en el teléfono",
        body: [
          "No hay cuenta ni servidor. El disco habla con el teléfono por Bluetooth y la app lo guarda todo en el teléfono.",
          "Está pensada para exportar los datos en CSV o JSON, escribirlos en Apple Health y borrarlos todos. Apple Health recibe datos solo si lo activas, y no se lee nada de él. La app no lleva analítica.",
        ],
      },
      {
        title: "Widgets que dicen su edad",
        body: [
          "Los widgets muestran las mismas puntuaciones en la pantalla de inicio y en la de bloqueo. Si un número tiene más de seis horas, dice cuántas; al día siguiente se atenúa, y a los tres días el widget deja de mostrar números.",
          "Las imágenes muestran la misma pantalla de inicio justo tras sincronizar, al día siguiente y cuatro días después.",
        ],
      },
    ],
    art: {
      tag: "Datos simulados.",
      note: "Capturas de la app real. Todas las cifras son inventadas.",
      today: {
        label: "Tres móviles con la pantalla Hoy de la app: anoche, ahora y la hoja de conclusiones levantada.",
        names: { today_night: "Anoche", today_now: "Ahora", today_sheet: "Conclusiones" },
      },
      trends: {
        label: "Dos móviles con la pantalla Tendencias: la recuperación en 30 días, y el pulso en reposo con un día señalado con el dedo.",
        names: { trends_readiness: "Recuperación, 30 días", trends_scrub: "Pulso en reposo" },
      },
      data: {
        label: "Tres móviles con la pestaña Dispositivo: la hoja de Apple Health, el disco conectado y la hoja para exportar o borrar los datos.",
        names: { device_health: "Apple Health", device: "El disco", device_data: "Tus datos" },
        flow: {
          label: "El disco envía sus lecturas al iPhone por Bluetooth. Desde el iPhone pueden ir a Apple Health o a un archivo CSV o JSON.",
          disc: "Disco",
          bluetooth: "Bluetooth",
          phone: "iPhone",
          health: "Apple Health",
          file: "CSV · JSON",
        },
      },
      widgets: {
        label: "Tres móviles con la misma pantalla de inicio: los widgets de Caseback justo tras sincronizar, al día siguiente con las cifras atenuadas y cuatro días después sin cifras.",
        names: { widgets_home_fresh: "Recién sincronizado", widgets_home_day: "Al día siguiente", widgets_home_days: "Cuatro días después" },
        note: "Los widgets son los de la app real, en una pantalla de inicio, con cifras inventadas. «Al día siguiente» y «cuatro días después» se consiguen dando a los datos una hora de sincronización más antigua.",
      },
    },
  },
  open: {
    title: "Código y licencias",
    plates: [
      {
        title: "Qué está publicado",
        body: [
          "El diseño, el código y las pruebas de Caseback están en un solo repositorio público. Puedes leerlo todo.",
          "Tres capas son de código abierto y se pueden usar para cualquier fin, también para vender productos. El hardware, el firmware y la app son de código disponible: puedes leerlos, ejecutarlos y cambiarlos, pero no usarlos para vender un producto que compita con Caseback.",
        ],
      },
      {
        title: "Qué permite la licencia",
        body: [
          "Las capas de código disponible usan la Functional Source License. Puedes usarlas para lo que quieras salvo un uso competidor, que es ofrecerlas dentro de un producto o servicio comercial que hace lo mismo que Caseback.",
          "Publicamos el código y los planos para que cualquiera pueda comprobar qué hace el disco y cómo está construido. La licencia evita que una copia llegue al mercado antes que el original. Cada versión pasa a Apache 2.0 a los dos años de publicarse, así que la restricción acaba.",
        ],
      },
      {
        title: "Pasa las pruebas tú mismo",
        body: [
          "Estos comandos pasan las pruebas en tu ordenador. Los de Python necesitan Python 3.12 o superior; el de Swift necesita un Mac.",
        ],
      },
    ],
    art: {
      map: {
        label: "Mapa del repositorio: seis grupos de carpetas en dos conjuntos, cada uno con su licencia.",
        groups: [
          {
            name: "Código disponible",
            terms: "Functional Source License (FSL 1.1). Puedes leerlo, ejecutarlo, cambiarlo y compartirlo, pero no en un producto que compita. Cada versión pasa a Apache 2.0 a los dos años de publicarse.",
            rows: [
              { name: "Hardware", detail: "Placa, carcasa y almohadilla de microsucción", paths: ["hardware/"], licence: "FSL 1.1" },
              { name: "Firmware", detail: "Zephyr en el nRF52840", paths: ["firmware/"], licence: "FSL 1.1" },
              { name: "App", detail: "iOS, SwiftUI", paths: ["apps/"], licence: "FSL 1.1" },
            ],
          },
          {
            name: "Código abierto",
            terms: "Puedes usarlo para cualquier fin, también para vender productos, conservando los avisos de licencia.",
            rows: [
              { name: "Protocolo", detail: "Los mensajes Bluetooth, byte a byte, en Python, Swift y C", paths: ["caseback-protocol/"], licence: "Apache 2.0" },
              { name: "Algoritmos", detail: "Pulso, HRV, sueño y pasos", paths: ["algorithms/"], licence: "Apache 2.0" },
              { name: "Herramientas, pruebas y web", detail: "Scripts que dibujan las ilustraciones y las capturas de la app, las pruebas y esta web", paths: ["tools/", "tests/", "web/"], licence: "Apache 2.0" },
            ],
          },
        ],
        note: "Las versiones en Swift y en C del protocolo están dentro de apps/ y firmware/ y mantienen la licencia Apache 2.0.",
      },
      terms: {
        label: "Línea de tiempo: las capas de código disponible están bajo la Functional Source License hasta dos años después de publicar cada versión, y bajo Apache 2.0 a partir de entonces. Las capas de código abierto tienen su licencia desde el principio.",
        start: "Publicación",
        end: "Dos años después",
        srcRow: "Código disponible",
        srcPhase: "Functional Source License",
        srcAfter: "Apache 2.0",
        openRow: "Código abierto",
        openPhase: "Apache 2.0",
        can: {
          title: "Puedes",
          items: [
            "Leer, ejecutar y cambiar el código y los planos.",
            "Construir un disco o una pulsera para ti.",
            "Usarlos para enseñar o para investigar sin ánimo de lucro.",
            "Cobrar por instalar o reparar un Caseback a alguien que también use los archivos con esta licencia.",
            "Compartir tus cambios, con la licencia incluida.",
          ],
        },
        cannot: {
          title: "No puedes",
          items: [
            "Vender un producto o servicio que haga lo mismo que Caseback usando estos archivos.",
            "Llamar Caseback a un producto que no es nuestro. Puedes decir que se basa en Caseback, que es compatible con él o que es un fork.",
            "Quitar la licencia ni los avisos de copyright de una copia que compartas.",
          ],
        },
        before: "Las versiones publicadas antes del 28 de octubre de 2026 conservan las licencias con que salieron: Apache 2.0 el software y CERN-OHL-S 2.0 el hardware.",
        full: "Leer la licencia completa",
      },
      verify: {
        label: "Comandos que pasan las pruebas.",
        rows: [
          { name: "Pruebas del protocolo", detail: "La implementación en Python, contra los bytes de referencia", cmd: "cd caseback-protocol/python && pip install -e \".[dev]\" && pytest" },
          { name: "Pruebas de pulso y HRV", detail: "Filtrado, detección de latidos y HRV", cmd: "cd algorithms/ppg && pip install -e \".[dev]\" && pytest" },
          { name: "Pruebas de pasos, sueño y recuperación", detail: "Modelos y reglas de pasos, sueño, temperatura de la piel y recuperación", cmd: "cd algorithms/wellness && pip install -e ../ppg -e \".[dev]\" && pytest" },
          { name: "Pruebas del protocolo en Swift", detail: "La implementación en Swift, contra los mismos bytes de referencia. Necesita un Mac", cmd: "cd apps/ios/CasebackProtocol && swift test" },
        ],
        note: "Cada comando se ejecuta desde la raíz del repositorio.",
        repo: "Abrir el repositorio",
        contribute: "Cómo contribuir",
      },
    },
  },
  waitlist: {
    title: "Lista de espera",
    body: "Deja tu correo para enterarte cuando haya grabaciones de la pulsera de prueba y, más adelante, prototipos que probar. Como mucho, un correo por etapa del plan.",
    label: "Correo",
    placeholder: "tu@ejemplo.com",
    submit: "Apuntarme",
    sending: "Enviando",
    sent: "Mira tu correo. Entras en la lista cuando abras el enlace de ese mensaje.",
    invalid: "Esa dirección de correo no parece correcta.",
    error: "No ha salido. Prueba otra vez en un minuto.",
    closed: "La lista se abre cuando la web tenga una dirección desde la que escribir.",
    consent: "Guardamos tu correo y tu idioma solo para escribirte sobre Caseback. Más detalle en el",
    privacy: "aviso de privacidad",
    confirmTitle: "Ya estás en la lista",
    confirmBody: "Gracias. Te escribiremos cuando haya algo que enseñar.",
    confirmFailed: "Este enlace no es válido o ha caducado. Vuelve a apuntarte.",
    unsubTitle: "Ya no estás en la lista",
    unsubBody: "Hemos borrado tu correo.",
    emailSubject: "Confirma tu correo para la lista de espera de Caseback",
    emailBody: "Abre este enlace para entrar en la lista de espera de Caseback:",
    emailIgnore: "Si no lo has pedido tú, ignora este mensaje y no se guardará nada.",
    emailUnsub: "Para salir de la lista cuando quieras:",
  },
  privacy: {
    title: "Aviso de privacidad",
    updated: "Actualizado el 27 de octubre de 2026",
    pending: "pendiente de fijar antes del lanzamiento",
    blocks: [
      { h: "Quién es responsable", p: ["El responsable del tratamiento es {controller}. Contacto: {email}."] },
      { h: "Qué datos guardamos", p: ["Solo para la lista de espera: tu correo, el idioma de la web que usaste y las fechas en que te apuntaste y confirmaste. La web no usa cookies ni analítica."] },
      { h: "Para qué y con qué base", p: ["Para escribirte sobre Caseback: los resultados de las pruebas, los prototipos y, si llega, una campaña. La base es tu consentimiento, que das al confirmar el correo."] },
      { h: "Quién los trata por nosotros", p: ["Resend envía los correos y Upstash guarda la lista. La web está alojada en Vercel, que guarda registros de acceso durante poco tiempo. Todos actúan siguiendo nuestras instrucciones con un contrato de encargo de tratamiento."] },
      { h: "Cuánto tiempo", p: ["Hasta que salgas de la lista o termine el proyecto. Los correos que nunca se confirman se borran a los 7 días."] },
      { h: "Tus derechos", p: ["Puedes salir de la lista desde cualquier correo y pedirnos acceder a tus datos, corregirlos o borrarlos en el contacto de arriba. También puedes reclamar ante la Agencia Española de Protección de Datos (aepd.es)."] },
    ],
  },
  notFound: { title: "Aquí no hay nada", body: "Esta página no existe.", home: "Volver a la tapa" },
};
