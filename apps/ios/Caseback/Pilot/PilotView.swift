import CasebackProtocol
import SwiftUI

struct PilotView: View {
  var onUnitReady: ((String) -> Void)?
  @StateObject private var radio: PilotRadio

  init(factoryTools: Bool = false, onUnitReady: ((String) -> Void)? = nil) {
    self.onUnitReady = onUnitReady
    _radio = StateObject(wrappedValue: PilotRadio(factoryTools: factoryTools))
  }

  var body: some View {
    NavigationStack {
      List {
        Section("Disco") {
          Text(radio.status)
          if radio.attached {
            Button("Desconectar") { radio.disconnect() }
          } else {
            if radio.savedDevices.isEmpty {
              Text("Para empezar, conecta la base al USB-C y coloca el disco con los contactos hacia abajo. Selecciona su nombre y acepta el enlace en el iPhone.")
                .font(.footnote)
            }
            Button("Buscar discos") { radio.scan() }.disabled(!radio.radioOn)
            ForEach(radio.devices, id: \.identifier) { p in
              Button(p.name ?? String(p.identifier.uuidString.prefix(8))) { radio.connect(p) }
            }
          }
        }
        if radio.ready {
          Section("Unidad") {
            LabeledContent("Identificador", value: radio.deviceID)
            LabeledContent("Terminal BAT", value: radio.battery)
            if radio.caps & CAPTemperature != 0 {
              LabeledContent("Temperatura del sensor", value: radio.temperature)
            }
            Button("Actualizar lecturas") { radio.refresh() }.disabled(radio.busy)
          }
          Section("Captura de banco") {
            stream("Luz verde", 1, CAPPPGRaw)
            if radio.enabled.contains(1) { PilotSignalChart(signals: radio.liveSignals, id: 1) }
            stream("Acelerómetro", 2, CAPAccel)
            if radio.enabled.contains(2) { PilotSignalChart(signals: radio.liveSignals, id: 2) }
            if radio.enabled.contains(1) && radio.enabled.contains(2) {
              PilotPulseView(signals: radio.liveSignals)
            } else if radio.caps & CAPPPGRaw != 0 && radio.caps & CAPAccel != 0 {
              Text("Para estimar el pulso en reposo, activa Luz verde y Acelerómetro.")
                .font(.footnote).foregroundStyle(.secondary)
            }
            LabeledContent("Discontinuidades detectadas", value: String(radio.gaps))
            Button("Preparar CSV") { radio.exportCapture() }.disabled(
              radio.samples.reduce(0, +) == 0)
          }
        }
        if !radio.savedDevices.isEmpty {
          Section("Actividad guardada") {
            if radio.savedDevices.count > 1 {
              Picker(
                "Unidad", selection: Binding(get: { radio.saved.device }, set: radio.selectArchive)
              ) {
                ForEach(radio.savedDevices, id: \.self) { Text($0).tag($0) }
              }
            } else {
              LabeledContent("Unidad", value: radio.saved.device)
            }
            LabeledContent("Periodos de 30 s", value: String(radio.saved.epochs))
            if !radio.ready, let bat = radio.saved.battery, let at = radio.saved.batteryAt {
              LabeledContent("Última lectura de BAT", value: bat)
              Text(at.formatted(date: .abbreviated, time: .shortened)).font(.caption)
            }
            if !radio.ready, let temp = radio.saved.temperature, let at = radio.saved.temperatureAt
            {
              LabeledContent("Última temperatura del sensor", value: temp)
              Text(at.formatted(date: .abbreviated, time: .shortened)).font(.caption)
            }
            if radio.saved.epochs > 0 {
              NavigationLink("Ver últimos periodos") {
                List(radio.recent) { e in
                  VStack(alignment: .leading, spacing: 4) {
                    if let utc = e.utc {
                      Text(
                        Date(timeIntervalSince1970: Double(utc) / 1000).formatted(
                          date: .abbreviated, time: .standard))
                    } else {
                      Text("Arranque \(e.boot) · \(e.uptime / 1000) s · sin hora UTC")
                    }
                    Text("\(e.activity) cambios de aceleración en 30 s").font(.subheadline)
                    if e.gap { Text("Discontinuidad previa").font(.caption) }
                  }
                }.navigationTitle("Actividad")
              }
              Text(
                "El disco cuenta cambios de aceleración. El pulso no se midió en estos periodos."
              ).font(.footnote)
              Button("Preparar CSV de actividad") { radio.exportCapture(daily: true) }.disabled(
                radio.exporting)
            }
            if radio.saved.boots > 1 {
              LabeledContent("Arranques registrados", value: String(radio.saved.boots))
            }
            if radio.saved.lost > 0 {
              LabeledContent(
                "Tramas ausentes en intervalos sobrescritos", value: String(radio.saved.lost))
            }
            if radio.saved.previouslyAcknowledged > 0 {
              LabeledContent(
                "Tramas confirmadas en un archivo previo",
                value: String(radio.saved.previouslyAcknowledged))
            }
            if radio.saved.interruptions > 0 {
              LabeledContent(
                "Discontinuidades en la medida", value: String(radio.saved.interruptions))
            }
            if radio.ready && radio.caps & CAPIBILog != 0 {
              Button("Sincronizar actividad") { radio.syncHistory() }.disabled(radio.busy)
            }
          }
          if !radio.captures.isEmpty {
            Section("Capturas guardadas") {
              ForEach(radio.captures) { c in
                Button {
                  radio.exportCapture(capture: c.id)
                } label: {
                  VStack(alignment: .leading) {
                    Text(
                      Date(timeIntervalSince1970: Double(c.utc) / 1000).formatted(
                        date: .abbreviated, time: .standard))
                    Text("\(c.n) muestras · Preparar CSV").font(.caption)
                  }
                }.disabled(radio.exporting)
              }
            }
          }
        }
        if radio.factoryAvailable {
          Section("Taller") {
            NavigationLink("Preparar entrega de esta unidad") { PilotFactoryView(radio: radio) }
          }
        }
        if !radio.factoryNotice.isEmpty { Text(radio.factoryNotice).font(.footnote) }
        if !radio.archiveNotice.isEmpty { Text(radio.archiveNotice).font(.footnote) }
        if let url = radio.exported { ShareLink("Compartir captura CSV", item: url) }
      }.navigationTitle("Caseback")
        .onChange(of: radio.ready) { _, ready in if ready { onUnitReady?(radio.deviceID) } }
    }
  }
  private func stream(_ title: String, _ id: UInt8, _ flag: UInt32) -> some View {
    HStack {
      VStack(alignment: .leading) {
        Text(title)
        Text("\(radio.samples[Int(id)]) muestras").font(.caption)
      }
      Spacer()
      if radio.caps & flag == 0 {
        Text("Sin detectar").foregroundStyle(.secondary)
      } else {
        Button(radio.enabled.contains(id) ? "Parar" : "Medir") { radio.toggle(id) }.disabled(
          radio.busy)
      }
    }
  }
}
