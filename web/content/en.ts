// English copy. Every figure here must match the repository (the design notes, section 2, and the
// algorithm READMEs); the tone follows the design notes.

export const en = {
  langName: "English",
  meta: {
    title: "Caseback",
    description:
      "A sensor under the watch you already wear, with its design and code published. A thin disc on the caseback measures pulse, sleep and movement for an iPhone app. It is an early prototype.",
  },
  nav: {
    home: "Caseback",
    back: "Back to the caseback",
    github: "GitHub",
    waitlist: "Waitlist",
    language: "Language",
    skip: "Skip the intro",
    plate: "Plate",
    of: "of",
    sections: "Sections",
  },
  home: {
    lead: "A sensor under the watch you already wear.",
    sub: "A 25 mm disc sticks to the back of your watch and measures pulse, sleep and movement.",
    side: {
      title: "From the side, on the wrist",
      watch: "Your watch",
      disc: "Caseback",
      wrist: "Wrist",
      label:
        "Side view: the disc sticks to the back of the watch and sits between the watch and the wrist.",
    },
    status: "Prototype phase",
    drawing:
      "Drawing of a watch that turns over and becomes the disc, shown in 3D: its parts come down into the shell one by one and the closed disc turns to its skin face. Lines lead from parts of the disc to the sections of this site.",
    callouts: {
      wear: { label: "How it's worn", part: "Microsuction pad" },
      measure: { label: "What it measures", part: "Sensor window" },
      app: { label: "The app", part: "Bluetooth antenna" },
      open: { label: "Code and licences", part: "Seam between shell and lid" },
    },
  },
  wear: {
    title: "How it's worn",
    plates: [
      {
        title: "Under the caseback",
        body: [
          "The disc sits between the back of the watch and the wrist. A microsuction pad holds it to the caseback: no glue on the watch and no magnet near the movement.",
          "From the outside the watch looks the same. The disc is designed to be 25 mm across and 3.1 mm thick.",
        ],
        art: { case: "Watch case", disc: "Disc", pad: "Pad", skin: "Wrist", thick: "3.1 mm" },
      },
      {
        title: "Charging, and the band",
        body: [
          "To charge, the watch lies dial up on a small round puck with the disc still stuck behind it. Two contacts on the skin face of the disc touch two spring pins in the puck.",
          "Without the watch, a fabric band holds the disc against the wrist for sleep or training.",
        ],
        art: { puck: "Charging puck", band: "Fabric band" },
      },
    ],
  },
  measure: {
    title: "What it measures",
    plates: [
      {
        title: "What the disc senses",
        body: [
          "Three small LEDs, green, red and infrared, shine into the skin under the disc, and a photodiode next to them measures how much of that light comes back. Blood absorbs light and the amount of blood under the sensor changes a little with every beat, so the returning light dips and recovers with the pulse.",
          "An accelerometer measures movement. It gives the steps and the sleep stages, and it tells the pulse algorithm which part of the signal is arm motion. A thermistor on the skin side reads skin temperature.",
          "There is no ECG. An ECG needs two contacts on different parts of the body, and a disc under a watch touches one wrist.",
        ],
      },
      {
        title: "Three answers and what they come from",
        body: [
          "The app opens on three answers: Recovery and Sleep, both from 0 to 100, and Movement, your steps against a usual day of yours.",
          "Each is built from signals the disc records. Recovery compares your resting heart rate, HRV, last night's sleep and skin temperature with your own last weeks. Sleep comes from motion and heart rate, and Movement from motion. Blood oxygen is shown on its own, as a trend.",
          "A filled mark is shown as a value and an open mark as a trend. Caseback is not a medical device and does not diagnose anything.",
        ],
      },
    ],
    art: {
      sense: {
        disc: "Disc",
        skin: "Skin",
        leds: "LEDs",
        pd: "Photodiode",
        green: "Green light",
        red: "Red light",
        ir: "Infrared light",
        ppgTitle: "What the photodiode reads",
        seconds: "s",
        label:
          "The disc on the skin. Green, red and infrared light from three LEDs travels through the skin and comes back to a photodiode. Below it, eight seconds of a recorded pulse waveform.",
        note: "Schematic. Distances and depths are not to scale; longer wavelengths reach deeper.",
        source: "The waveform is a finger recording from a hospital monitor (BIDMC, subject 36, public data). It is not from the disc.",
      },
      signals: {
        recovery: "Recovery",
        recoverySub: "0 to 100",
        sleep: "Sleep",
        sleepSub: "0 to 100",
        movement: "Movement",
        movementSub: "steps against your usual day",
        hr: "Heart rate",
        hrv: "HRV",
        temp: "Skin temperature",
        spo2: "Blood oxygen",
        motion: "Motion",
        label:
          "The three answers of the app, Recovery, Sleep and Movement, joined by lines to the signals they are built from. Heart rate, HRV, sleep and steps are filled marks; skin temperature and blood oxygen are open marks: the app shows them as trends.",
        headAnswers: "Answers",
        headSignals: "Signals",
        legendFilled: "Filled mark: shown as a value",
        legendOpen: "Open mark: shown as a trend",
      },
    },
  },
  app: {
    title: "The app",
    plates: [
      {
        title: "Today",
        body: [
          "The first screen answers how you slept and how recovered you are. The score comes first, then one sentence, then the chart behind it.",
          "The app is for iPhone; Android comes later.",
        ],
      },
      {
        title: "Trends",
        body: [
          "Trends sets the last 7, 30 or 90 days against your own usual. The dotted line is your median and the faint band behind the line is your usual range. Hold a finger on the chart to read any day.",
          "Each score and each measurement opens its own screen, with a sentence on what usually affects it.",
        ],
      },
      {
        title: "Your data stays on the phone",
        body: [
          "There is no account and no server. The disc talks to the phone over Bluetooth and the app keeps everything on the phone.",
          "It is designed to export the data as CSV or JSON, write it to Apple Health and delete all of it. Apple Health receives data only if you switch it on, and nothing is read from it. The app has no analytics.",
        ],
      },
      {
        title: "Widgets that say their age",
        body: [
          "Widgets show the same scores on the Home Screen and the Lock Screen. A number older than six hours says how old it is, it dims the next day, and after three days the widget stops showing numbers.",
          "The pictures show the same Home Screen just after a sync, the next day and four days later.",
        ],
      },
    ],
    art: {
      tag: "Simulated data.",
      note: "Screens from the real app. Every number is invented.",
      today: {
        label: "Three phones showing the Today screen of the app: last night, now, and the conclusions sheet pulled up.",
        names: { today_night: "Last night", today_now: "Now", today_sheet: "Conclusions" },
      },
      trends: {
        label: "Two phones showing the Trends screen: recovery over 30 days, and resting heart rate with one day held under the finger.",
        names: { trends_readiness: "Recovery, 30 days", trends_scrub: "Resting heart rate" },
      },
      data: {
        label: "Three phones showing the Device tab: the Apple Health sheet, the disc connected, and the sheet to export or delete the data.",
        names: { device_health: "Apple Health", device: "The disc", device_data: "Your data" },
        flow: {
          label: "The disc sends its readings to the iPhone over Bluetooth. From the iPhone they can go to Apple Health or to a CSV or JSON file.",
          disc: "Disc",
          bluetooth: "Bluetooth",
          phone: "iPhone",
          health: "Apple Health",
          file: "CSV · JSON",
        },
      },
      widgets: {
        label: "Three phones with the same Home Screen: the Caseback widgets just after a sync, the next day with dimmed numbers, and four days later with no numbers.",
        names: { widgets_home_fresh: "Just synced", widgets_home_day: "The next day", widgets_home_days: "Four days later" },
        note: "The widgets are the real app's own, on a Home Screen, with invented numbers. The next day and four days later are made by giving the data an older sync time.",
      },
    },
  },
  open: {
    title: "Code and licences",
    plates: [
      {
        title: "What is published",
        body: [
          "The design, code and tests of Caseback are in one public repository. You can read all of it.",
          "Three layers are open source and can be used for any purpose, selling products included. Hardware, firmware and the app are source-available: you can read, run and change them, but not use them to sell a product that competes with Caseback.",
        ],
      },
      {
        title: "What the licence allows",
        body: [
          "The source-available layers use the Functional Source License. You can use them for anything except a competing use, which means making them available in a commercial product or service that does the same job as Caseback.",
          "We publish the code and the drawings so that anyone can check what the disc does and how it is built. The licence keeps a copy from reaching the market before the original does. Each version becomes Apache 2.0 two years after it is published, so the restriction ends.",
        ],
      },
      {
        title: "Run the tests yourself",
        body: [
          "These commands run the tests on your own computer. The Python ones need Python 3.12 or newer; the Swift one needs a Mac.",
        ],
      },
    ],
    art: {
      map: {
        label: "Map of the repository: six groups of folders in two sets, each with its licence.",
        groups: [
          {
            name: "Source-available",
            terms: "Functional Source License (FSL 1.1). Read, run, change and share it, but not in a competing product. Each version becomes Apache 2.0 two years after it is published.",
            rows: [
              { name: "Hardware", detail: "Board, enclosure and microsuction pad", paths: ["hardware/"], licence: "FSL 1.1" },
              { name: "Firmware", detail: "Zephyr on the nRF52840", paths: ["firmware/"], licence: "FSL 1.1" },
              { name: "App", detail: "iOS, SwiftUI", paths: ["apps/"], licence: "FSL 1.1" },
            ],
          },
          {
            name: "Open source",
            terms: "Use it for any purpose, selling products included, keeping the licence notices.",
            rows: [
              { name: "Protocol", detail: "The Bluetooth messages, byte by byte, in Python, Swift and C", paths: ["caseback-protocol/"], licence: "Apache 2.0" },
              { name: "Algorithms", detail: "Pulse, HRV, sleep and steps", paths: ["algorithms/"], licence: "Apache 2.0" },
              { name: "Tools, tests and website", detail: "Scripts that draw the illustrations and the app captures, the tests and this site", paths: ["tools/", "tests/", "web/"], licence: "Apache 2.0" },
            ],
          },
        ],
        note: "The Swift and C versions of the protocol sit inside apps/ and firmware/ and keep the Apache 2.0 licence.",
      },
      terms: {
        label: "Timeline: the source-available layers are under the Functional Source License until two years after each version is published, and under Apache 2.0 from then on. The open source layers are under their licence from the start.",
        start: "Published",
        end: "Two years later",
        srcRow: "Source-available",
        srcPhase: "Functional Source License",
        srcAfter: "Apache 2.0",
        openRow: "Open source",
        openPhase: "Apache 2.0",
        can: {
          title: "You can",
          items: [
            "Read, run and change the code and the drawings.",
            "Build a disc or a bracelet for yourself.",
            "Use them to teach or for non-commercial research.",
            "Charge for installing or repairing a Caseback for someone who also uses the files under this licence.",
            "Share your changes, with the licence attached.",
          ],
        },
        cannot: {
          title: "You cannot",
          items: [
            "Sell a product or service that does the same job as Caseback using these files.",
            "Call a product Caseback if it is not ours. You may say it is based on, compatible with or a fork of Caseback.",
            "Remove the licence or the copyright notices from a copy you share.",
          ],
        },
        before: "Versions published before 28 October 2026 keep the licences they came with: Apache 2.0 for the software and CERN-OHL-S 2.0 for the hardware.",
        full: "Read the full licence",
      },
      verify: {
        label: "Commands that run the tests.",
        rows: [
          { name: "Protocol tests", detail: "The Python implementation, against the reference bytes", cmd: "cd caseback-protocol/python && pip install -e \".[dev]\" && pytest" },
          { name: "Pulse and HRV tests", detail: "Filtering, beat detection and HRV", cmd: "cd algorithms/ppg && pip install -e \".[dev]\" && pytest" },
          { name: "Steps, sleep and readiness tests", detail: "Models and rules for steps, sleep, skin temperature and readiness", cmd: "cd algorithms/wellness && pip install -e ../ppg -e \".[dev]\" && pytest" },
          { name: "Swift protocol tests", detail: "The Swift implementation, against the same reference bytes. Needs a Mac", cmd: "cd apps/ios/CasebackProtocol && swift test" },
        ],
        note: "Each command runs from the root of the repository.",
        repo: "Open the repository",
        contribute: "How to contribute",
      },
    },
  },
  waitlist: {
    title: "Waitlist",
    body: "Leave an email to hear when there are recordings from the test bracelet and, later, prototypes to try. At most one email per stage of the plan.",
    label: "Email",
    placeholder: "you@example.com",
    submit: "Join",
    sending: "Sending",
    sent: "Check your inbox. You are on the list once you open the link in that email.",
    invalid: "That email address does not look right.",
    error: "It did not go through. Try again in a minute.",
    closed: "The list opens once the site has an address to send from.",
    consent: "We keep your email and language only to write to you about Caseback. Details in the",
    privacy: "privacy notice",
    confirmTitle: "You are on the list",
    confirmBody: "Thanks. You will hear from us when there is something to show.",
    confirmFailed: "This link is not valid or has expired. Join the list again.",
    unsubTitle: "You are off the list",
    unsubBody: "Your email has been deleted.",
    emailSubject: "Confirm your Caseback waitlist email",
    emailBody: "Open this link to join the Caseback waitlist:",
    emailIgnore: "If you did not ask for this, ignore this email and nothing is stored.",
    emailUnsub: "To leave the list at any time:",
  },
  privacy: {
    title: "Privacy notice",
    updated: "Last updated 27 October 2026",
    pending: "to be set before launch",
    blocks: [
      { h: "Who is responsible", p: ["The data controller is {controller}. Contact: {email}."] },
      { h: "What we collect", p: ["Only for the waitlist: your email, the site language you used, and the dates you joined and confirmed. The site sets no cookies and runs no analytics."] },
      { h: "Why and on what basis", p: ["To email you about Caseback: the test results, prototypes and, if it happens, a campaign. The basis is your consent, given when you confirm your email."] },
      { h: "Who handles it for us", p: ["Resend sends the emails and Upstash stores the list. The site is hosted on Vercel, which keeps short-lived request logs. Each acts on our instructions under a data processing agreement."] },
      { h: "How long", p: ["Until you leave the list or the project ends. Addresses that are never confirmed are deleted after 7 days."] },
      { h: "Your rights", p: ["You can leave the list from any email, and ask us to access, correct or delete your data at the contact above. You can also complain to your data protection authority; in Spain, the AEPD (aepd.es)."] },
    ],
  },
  notFound: { title: "Nothing here", body: "This page does not exist.", home: "Back to the caseback" },
};
