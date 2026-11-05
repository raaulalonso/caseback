import CasebackProtocol
import CoreBluetooth
import SwiftUI

/// All CoreBluetooth delegate callbacks and UI actions run on the main queue.
final class PilotRadio: NSObject, ObservableObject, CBCentralManagerDelegate, CBPeripheralDelegate {
  @Published var status = "Bluetooth"
  @Published var devices: [CBPeripheral] = []
  @Published var deviceID = ""
  @Published var battery = ""
  @Published var temperature = ""
  @Published var samples = [0, 0, 0]
  @Published var enabled = Set<UInt8>()
  @Published var caps: UInt32 = 0
  @Published var ready = false
  @Published var attached = false
  @Published var busy = false
  @Published var radioOn = false
  @Published var gaps = 0
  @Published var exported: URL?
  let liveSignals = PilotLiveSignals()
  private var central: CBCentralManager!
  private var peer: CBPeripheral?
  private let service = CBUUID(string: GATTServiceUUID), dataID = CBUUID(string: GATTDataUUID)
  private let controlID = CBUUID(string: GATTControlUUID), ess = CBUUID(string: "181A"),
    tempID = CBUUID(string: "2A6E")
  private var control: CBCharacteristic?, dataChar: CBCharacteristic?, tempChar: CBCharacteristic?
  private var pending: (UInt8, Data)?, timeout: DispatchWorkItem?
  private var startUTC: Double = 0, anchorUTC: Double = 0, anchor: TimeAnchorReply?
  private var sequence: UInt16?
  @Published var archiveNotice = ""
  @Published var savedDevices: [String] = []
  @Published var saved = ArchiveSummary()
  @Published var recent: [StoredEpoch] = []
  @Published var captures: [StoredCapture] = []
  @Published var exporting = false
  private var archive: PilotArchive?
  private var session = UUID().uuidString
  private var requestedCursor: UInt32?, replay: ReplayWindow?, syncEnd: UInt32?
  private var retries = 0, closing = false
  private var syncStart: UInt32?
  private var pendingAck: Data?
  private var nextSync: DispatchWorkItem?
  private var lastAnchorAt = Date.distantPast
  private var autoReconnect = true
  private let preferredPeerKey = "pilot.preferredPeer"
  private static let pageSize: UInt16 = 16

  private let factoryTools: Bool
  private var factoryChar: CBCharacteristic?
  private var releasePeer: UUID?
  private let handedOffKey = "pilot.factoryHandedOff"
  private func reserveForRecipient(_ id: UUID, _ reserve: Bool) {
    var ids = Set(UserDefaults.standard.stringArray(forKey: handedOffKey) ?? [])
    if reserve { ids.insert(id.uuidString) } else { ids.remove(id.uuidString) }
    UserDefaults.standard.set(ids.sorted(), forKey: handedOffKey)
  }
  private func heldForRecipient(_ id: UUID) -> Bool {
    factoryTools && (UserDefaults.standard.stringArray(forKey: handedOffKey) ?? []).contains(id.uuidString)
  }
  @Published private(set) var factoryAvailable = false
  @Published private(set) var factoryNotice = ""

  init(factoryTools: Bool = false) {
    self.factoryTools = factoryTools
    super.init()
    do {
      archive = try PilotArchive.openDefault()
      reloadArchive()
    } catch { archiveNotice = error.localizedDescription }
    central = CBCentralManager(delegate: self, queue: .main)
  }
  func centralManagerDidUpdateState(_ central: CBCentralManager) {
    radioOn = central.state == .poweredOn
    if !radioOn {
      endSession()
      devices = []
      status = "Bluetooth no disponible (estado \(central.state.rawValue))."
    } else {
      status = "Coloca el disco en la base para el primer enlace."
      scan()
    }
  }
  func scan() {
    guard radioOn, peer == nil else { return }
    devices = []
    central.scanForPeripherals(withServices: [service], options: nil)
    status = "Buscando discos…"
  }
  func centralManager(
    _ central: CBCentralManager, didDiscover p: CBPeripheral, advertisementData: [String: Any],
    rssi RSSI: NSNumber
  ) {
    if !devices.contains(where: { $0.identifier == p.identifier }) { devices.append(p) }
    if peer == nil, autoReconnect,
      UserDefaults.standard.string(forKey: preferredPeerKey) == p.identifier.uuidString
    {
      connect(p)
    }
  }
  func connect(_ p: CBPeripheral) {
    guard peer == nil else { return }
    if heldForRecipient(p.identifier) {
      factoryNotice = "Esta unidad se reservó para entrega. Usa Caseback de presentación para el nuevo enlace."
      return
    }
    factoryNotice = ""
    autoReconnect = true
    central.stopScan()
    peer = p
    p.delegate = self
    attached = true
    status = "Conectando…"
    armTimeout("El disco no respondió. Comprueba la base y vuelve a conectar.", seconds: 40)
    central.connect(p)
  }
  func disconnect() {
    liveSignals.bind(nil)
    autoReconnect = false
    closing = true
    if let p = peer { central.cancelPeripheralConnection(p) }
  }
  private func armTimeout(_ message: String, seconds: Double = 15) {
    timeout?.cancel()
    let task = DispatchWorkItem { [weak self] in
      guard let self else { return }
      if self.requestedCursor != nil { self.retryHistory(message) } else { self.fail(message) }
    }
    timeout = task
    DispatchQueue.main.asyncAfter(deadline: .now() + seconds, execute: task)
  }
  private func endSession() {
    liveSignals.bind(nil)
    timeout?.cancel()
    pending = nil
    expecting = nil
    pendingAck = nil
    requestedCursor = nil
    replay = nil
    syncEnd = nil
    nextSync?.cancel()
    closing = false
    syncStart = nil
    busy = false
    factoryAvailable = false
    factoryChar = nil
    ready = false
    attached = false
    reloadArchive(unit: deviceID)
    peer = nil
    control = nil
    dataChar = nil
    tempChar = nil
    enabled = []
    sequence = nil
    anchor = nil
  }
  func centralManager(_ central: CBCentralManager, didConnect p: CBPeripheral) {
    guard p == peer else { return }
    status = "Descubriendo servicios. Acepta el enlace en el iPhone."
    samples = [0, 0, 0]
    gaps = 0
    session = UUID().uuidString
    exported = nil
    deviceID = ""
    caps = 0
    battery = ""
    temperature = ""
    let services = factoryTools ? [service, ess, CBUUID(string: PilotFactory.service)] : [service, ess]
    p.discoverServices(services)
  }
  func centralManager(_ central: CBCentralManager, didFailToConnect p: CBPeripheral, error: Error?)
  {
    guard p == peer else { return }
    endSession()
    status = error?.localizedDescription ?? "No se pudo conectar."
  }
  func centralManager(
    _ central: CBCentralManager, didDisconnectPeripheral p: CBPeripheral, error: Error?
  ) {
    guard p == peer else { return }
    if releasePeer == p.identifier {
      releasePeer = nil
      factoryNotice = "Se perdió el enlace durante la entrega. Comprueba el resultado con la base y un segundo iPhone."
    }
    endSession()
    if autoReconnect {
      scan()
    } else if let error {
      status = error.localizedDescription
    } else {
      status += " · Desconectado."
    }
  }
  private func retryHistory(_ reason: String) {
    guard let peer, retries < 2 else {
      fail(reason)
      return
    }
    guard !closing else { return }
    closing = true
    timeout?.cancel()
    retries += 1
    archiveNotice = reason + " Se reanudará desde la última trama guardada."
    autoReconnect = true
    central.cancelPeripheralConnection(peer)
  }
  private func fail(_ message: String) {
    status = message
    disconnect()
  }
  func peripheral(_ p: CBPeripheral, didDiscoverServices error: Error?) {
    guard p == peer else { return }
    guard error == nil, let svcs = p.services, svcs.contains(where: { $0.uuid == service }) else {
      fail("Servicio del disco ausente.")
      return
    }
    for svc in svcs {
      if factoryTools && svc.uuid == CBUUID(string: PilotFactory.service) {
        p.discoverCharacteristics([CBUUID(string: PilotFactory.characteristic)], for: svc)
      }
      if svc.uuid == service { p.discoverCharacteristics([controlID, dataID], for: svc) }
      if svc.uuid == ess { p.discoverCharacteristics([tempID], for: svc) }
    }
  }
  func peripheral(_ p: CBPeripheral, didDiscoverCharacteristicsFor svc: CBService, error: Error?) {
    guard p == peer else { return }
    if svc.uuid == CBUUID(string: PilotFactory.service) {
      guard factoryTools, error == nil else { return }
      factoryChar = svc.characteristics?.first { ch in
        ch.uuid == CBUUID(string: PilotFactory.characteristic) && ch.properties.contains([.read, .write])
      }
      if ready, let ch = factoryChar { p.readValue(for: ch) }
      return
    }
    if svc.uuid == ess {
      tempChar = svc.characteristics?.first(where: { $0.uuid == tempID })
      return
    }
    guard error == nil, let ch = svc.characteristics,
      let ctl = ch.first(where: {
        $0.uuid == controlID && $0.properties.contains(.writeWithoutResponse)
      }),
      let stream = ch.first(where: { $0.uuid == dataID && $0.properties.contains(.notify) })
    else {
      fail("No se encontraron los canales BLE del disco.")
      return
    }
    control = ctl
    dataChar = stream
    p.setNotifyValue(true, for: stream)
  }
  func peripheral(
    _ p: CBPeripheral, didUpdateNotificationStateFor ch: CBCharacteristic, error: Error?
  ) {
    guard p == peer, ch == dataChar else { return }
    guard error == nil, ch.isNotifying else {
      fail("No se pudo enlazar. Pon el disco en la base.")
      return
    }
    request(MSGInfoRequest)
  }
  private func request(_ type: UInt8, _ bytes: Data = Data()) {
    guard !busy, peer != nil, let wire = try? Frame(msgType: type, payload: bytes).encoded() else {
      return
    }
    busy = true
    pending = (type, wire)
    armTimeout("Sin respuesta del disco.")
    transmit()
  }
  private var expecting: UInt8?
  private func transmit() {
    guard let p = peer, let ctl = control, p.canSendWriteWithoutResponse else { return }
    if let ack = pendingAck {
      pendingAck = nil
      p.writeValue(ack, for: ctl, type: .withoutResponse)
    }
    guard let (type, wire) = pending, p.canSendWriteWithoutResponse else { return }
    guard wire.count <= p.maximumWriteValueLength(for: .withoutResponse) else {
      fail("MTU insuficiente.")
      return
    }
    pending = nil
    expecting = type == MSGInfoRequest ? MSGInfoResponse : type
    if type == MSGTimeAnchor { startUTC = Date().timeIntervalSince1970 * 1000 }
    p.writeValue(wire, for: ctl, type: .withoutResponse)
  }
  func peripheralIsReady(toSendWriteWithoutResponse p: CBPeripheral) { if p == peer { transmit() } }
  private func reloadArchive(unit: String = "") {
    guard let archive else { return }
    do {
      savedDevices = try archive.devices()
      let selected = !unit.isEmpty ? unit : savedDevices.first ?? ""
      if !selected.isEmpty {
        saved = try archive.summary(selected)
        recent = try archive.recent(selected)
        captures = try archive.captures(selected)
      }
    } catch { archiveNotice = error.localizedDescription }
  }
  func selectArchive(_ unit: String) {
    reloadArchive(unit: unit)
    exported = nil
  }
  func releaseFactoryUnit(_ token: Data) {
    guard factoryTools, factoryAvailable, ready, !busy, !closing, releasePeer == nil,
      enabled.isEmpty, token.count == 16, let peer, let ch = factoryChar else {
      factoryNotice = "Termina las capturas y espera a que finalice la sincronización."
      return
    }
    // A disconnect can arrive before the write callback. Never let this phone reclaim the unit.
    autoReconnect = false
    if UserDefaults.standard.string(forKey: preferredPeerKey) == peer.identifier.uuidString {
      UserDefaults.standard.removeObject(forKey: preferredPeerKey)
    }
    reserveForRecipient(peer.identifier, true)
    releasePeer = peer.identifier
    busy = true
    factoryAvailable = false
    factoryNotice = "Enviando la orden de entrega…"
    nextSync?.cancel()
    peer.writeValue(token, for: ch, type: .withResponse)
  }

  func peripheral(_ p: CBPeripheral, didWriteValueFor ch: CBCharacteristic, error: Error?) {
    guard factoryTools, p == peer, releasePeer == p.identifier, ch == factoryChar else { return }
    releasePeer = nil
    if let error {
      busy = false
      let att = error as NSError
      if att.domain == CBATTErrorDomain && [0x03, 0x08, 0x0D].contains(att.code) {
        reserveForRecipient(p.identifier, false)
        factoryNotice = "El disco rechazó la entrega. Revisa la base y el código de esta unidad."
      } else {
        factoryNotice = "Respuesta de entrega incierta. Verifica el estado con el procedimiento del taller."
      }
      p.readValue(for: ch)
      scheduleSync()
      return
    }
    closing = true
    liveSignals.bind(nil)
    factoryNotice = "Orden aceptada. Espera a que el disco se desconecte. Retíralo para embalarlo y vuelve a ponerlo en la base con el iPhone del destinatario para el primer enlace."
  }

  func refresh() {
    guard ready, !busy else { return }
    request(MSGBattery)
    if let t = tempChar { peer?.readValue(for: t) }
  }
  func toggle(_ id: UInt8) {
    guard ready, !busy else { return }
    request(MSGStreamControl, Data([id, enabled.contains(id) ? 0 : 1, 1]))
  }
  func peripheral(_ p: CBPeripheral, didUpdateValueFor ch: CBCharacteristic, error: Error?) {
    guard p == peer, !closing else { return }
    if ch == factoryChar {
      factoryAvailable = factoryTools && ready && error == nil && PilotFactory.armed(ch.value)
        && !heldForRecipient(p.identifier)
      return
    }
    if ch == tempChar {
      if error == nil, let v = ch.value, v.count == 2 {
        let raw = Int16(bitPattern: UInt16(v[v.startIndex]) | UInt16(v[v.startIndex + 1]) << 8)
        temperature = String(format: "%.2f °C", Double(raw) / 100)
        if ready {
          do { try archive?.lastReading(.temperature, value: temperature, unit: deviceID) } catch {
            archiveNotice = error.localizedDescription
          }
        }
      } else {
        temperature = "Sin lectura"
      }
      return
    }
    guard ch == dataChar, error == nil, let value = ch.value else {
      fail("No se pudo leer el disco.")
      return
    }
    do {
      let f = try decodeFrame(value)
      if f.msgType == MSGStreamData {
        if f.payload.count > 16, f.payload[f.payload.startIndex + 16] & 1 != 0 {
          try recordHistory(f)
        } else {
          try record(f)
        }
        return
      }
      if f.msgType == MSGError {
        let e = try decodeErrorMessage(f)
        timeout?.cancel()
        busy = false
        expecting = nil
        status = String(format: "El disco rechazó 0x%02X (código 0x%04X).", e.msgType, e.code)
        if e.msgType == MSGHistoryQuery || e.msgType == MSGHistoryAck {
          archiveNotice =
            e.code == 0x0204
            ? "El disco ha rechazado el cursor guardado. Se conservan los registros del iPhone. Revisa si se borró la memoria de la unidad."
            : status
          fail(archiveNotice)
        } else if !ready {
          disconnect()
        } else if e.msgType == MSGBattery, caps & CAPIBILog != 0 {
          syncHistory()
        }
        return
      }
      guard busy, f.msgType == expecting else { return }
      busy = false
      timeout?.cancel()
      expecting = nil
      switch f.msgType {
      case MSGInfoResponse:
        let i = try decodeInfoResponse(f)
        caps = i.capabilities
        deviceID = i.deviceId.map { String(format: "%02X", $0) }.joined()
        guard caps & CAPEncryptedOnly != 0 else {
          fail("El disco no exige cifrado.")
          return
        }
        request(
          MSGTimeAnchor,
          try TimeAnchorRequest(utcMs: UInt64(Date().timeIntervalSince1970 * 1000)).payload())
      case MSGTimeAnchor:
        anchor = try decodeTimeAnchorReply(f)
        anchorUTC = (startUTC + Date().timeIntervalSince1970 * 1000) / 2
        guard let anchor, let ticks = Int64(exactly: anchor.uptimeMs), let archive else {
          throw ArchiveError.unavailable
        }
        try archive.saveAnchor(
          unit: deviceID, boot: anchor.bootId, ticks: ticks, utc: Int64(anchorUTC.rounded()))
        if let peer {
          UserDefaults.standard.set(peer.identifier.uuidString, forKey: preferredPeerKey)
        }
        liveSignals.bind(.init(unit: deviceID, session: session, boot: anchor.bootId))
        lastAnchorAt = Date()
        reloadArchive(unit: deviceID)
        ready = true
        if let ch = factoryChar { p.readValue(for: ch) }
        status = "Disco conectado."
        refresh()
      case MSGBattery:
        let b = try decodeBatteryFrame(f)
        let state: [UInt8: String] = [
          0: "sin carga", 1: "cargando", 2: "carga completa", 3: "fallo",
          255: "estado indeterminado",
        ]
        battery = "\(b.voltageMv) mV · \(state[b.charging] ?? "desconocido")"
        try archive?.lastReading(.battery, value: battery, unit: deviceID)
        if caps & CAPIBILog != 0 { syncHistory() }
      case MSGHistoryQuery:
        try beginPage(f)
      case MSGStreamControl:
        let b = [UInt8](f.payload)
        guard b.count == 3, [UInt8(1), 2].contains(b[0]), b[1] < 2, b[2] == 1 else {
          throw CaptureError.packet
        }
        if b[1] == 1 {
          enabled.insert(b[0])
        } else {
          enabled.remove(b[0])
          liveSignals.stop(b[0])
          reloadArchive(unit: deviceID)
          exportCapture()
        }
      default: break
      }
    } catch ArchiveError.sequence {
      retryHistory(ArchiveError.sequence.localizedDescription)
    } catch {
      let reason =
        (error as? ArchiveError)?.localizedDescription
        ?? "Trama no válida o transferencia incompleta."
      archiveNotice = reason
      fail(reason)
    }
  }
  func syncHistory() {
    guard ready, !busy, caps & CAPIBILog != 0 else { return }
    do {
      guard let archive else { throw ArchiveError.unavailable }
      requestedCursor = try archive.cursor(deviceID)
      guard let requestedCursor else { return }
      var bytes = word(requestedCursor)
      bytes.append(UInt8(Self.pageSize))
      bytes.append(0)
      request(MSGHistoryQuery, bytes)
    } catch {
      archiveNotice = error.localizedDescription
      fail(archiveNotice)
    }
  }

  private func word(_ value: UInt32) -> Data {
    Data((0..<4).map { UInt8(truncatingIfNeeded: value >> (8 * $0)) })
  }

  private func beginPage(_ frame: Frame) throws {
    guard let requestedCursor, let archive else { throw ArchiveError.cursor }
    let page = try HistoryPage(frame, requested: requestedCursor)
    try archive.acceptPage(page, requested: requestedCursor, unit: deviceID)
    if syncEnd == nil {
      syncEnd = page.next
      syncStart = page.first
    }
    if let end = syncEnd, let start = syncStart, start < end {
      archiveNotice =
        "Sincronizando actividad: \(min(page.first, end) - start) de \(end - start) tramas."
    }
    let window = ReplayWindow(page: page, limit: Self.pageSize)
    replay = window
    if window.next == window.end {
      try finishPage()
      return
    }
    busy = true
    armTimeout("Se interrumpió el historial. Vuelve a conectar para reanudar.")
  }

  private func recordHistory(_ frame: Frame) throws {
    let batch = try DailyFrame(frame)
    guard busy, var window = replay, let archive else { throw ArchiveError.cursor }
    try window.receive(batch, after: sequence, archive: archive, unit: deviceID)
    sequence = batch.seq
    replay = window
    if window.next == window.end {
      try finishPage()
    } else {
      armTimeout("Se interrumpió el historial. Vuelve a conectar para reanudar.")
    }
  }

  private func finishPage() throws {
    guard let pos = replay?.next, let end = syncEnd else { throw ArchiveError.cursor }
    timeout?.cancel()
    busy = false
    replay = nil
    requestedCursor = nil
    pendingAck = try Frame(msgType: MSGHistoryAck, payload: word(pos)).encoded()
    transmit()
    if pos < end {
      syncHistory()
      return
    }
    syncEnd = nil
    syncStart = nil
    retries = 0
    reloadArchive(unit: deviceID)
    archiveNotice = "Historial sincronizado."
    scheduleSync()
  }

  private func scheduleSync() {
    nextSync?.cancel()
    let work = DispatchWorkItem { [weak self] in
      guard let self, self.ready else { return }
      if self.busy {
        self.scheduleSync()
        return
      }
      if Date().timeIntervalSince(self.lastAnchorAt) >= 3600 {
        do {
          self.request(
            MSGTimeAnchor,
            try TimeAnchorRequest(utcMs: UInt64(Date().timeIntervalSince1970 * 1000)).payload())
        } catch { self.fail("No se pudo actualizar el reloj del disco.") }
      } else {
        self.syncHistory()
      }
    }
    nextSync = work
    DispatchQueue.main.asyncAfter(deadline: .now() + 30, execute: work)
  }

  private func record(_ frame: Frame) throws {
    let b = try PilotBatch(frame)
    guard let anchor, anchor.bootId == b.boot, let archive else { throw CaptureError.packet }
    let missing = sequence.map { $0 &+ 1 != b.seq } ?? (b.seq != 0)
    // A missing notification during backfill could be a history frame. Reconnect from the last commit.
    if missing && replay != nil { throw ArchiveError.sequence }
    let elapsed = Double(b.uptime) - Double(anchor.uptimeMs)
    guard abs(elapsed) < 7 * 86400 * 1000 else { throw CaptureError.packet }
    try archive.live(
      frame, batch: b, unit: deviceID, session: session,
      utc: Int64((anchorUTC + elapsed).rounded()), gap: missing || b.gap)
    sequence = b.seq
    if missing || b.gap { gaps += 1 }
    if enabled.contains(b.id) {
      liveSignals.receive(b, from: .init(unit: deviceID, session: session, boot: anchor.bootId),
                          missing: missing, at: ProcessInfo.processInfo.systemUptime)
    }
    samples[Int(b.id)] += b.values.count
  }

  func exportCapture(daily: Bool = false, capture: String? = nil) {
    guard let archive, !saved.device.isEmpty, !exporting else { return }
    exporting = true
    let url = archive.url
    let unit = saved.device
    let selected = capture ?? (attached && !daily && unit == deviceID ? session : nil)
    DispatchQueue.global(qos: .utility).async {
      let result = Result {
        try PilotArchive(url: url).export(unit: unit, daily: daily, session: selected)
      }
      DispatchQueue.main.async { [weak self] in
        guard let self else { return }
        self.exporting = false
        switch result {
        case .success(let file): self.exported = file
        case .failure(let error): self.archiveNotice = error.localizedDescription
        }
      }
    }
  }
}
enum CaptureError: Error { case packet }
struct PilotBatch {
  let boot: UInt32, uptime: UInt64, seq: UInt16, rate: UInt16, gap: Bool, id: UInt8, values: [PilotSample]
  var rows: [String] { values.map(\.csv) }
  func offsetMs(_ index: Int) -> UInt64 { UInt64((Double(index) * 10000 / Double(rate)).rounded()) }
  init(_ frame: Frame) throws {
    let p = [UInt8](frame.payload)
    guard frame.msgType == MSGStreamData, p.count >= 20, [UInt8(1), 2].contains(p[14]), p[15] == 1,
      p[16] & ~2 == 0
    else { throw CaptureError.packet }
    func u(_ at: Int, _ n: Int) -> UInt64 {
      (0..<n).reduce(UInt64(0)) { $0 | (UInt64(p[at + $1]) << (8 * $1)) }
    }
    let stride = p[14] == 1 ? 3 : 6
    let n = Int(p[19])
    let hz = u(17, 2)
    guard n > 0, hz > 0, p.count == 20 + n * stride else { throw CaptureError.packet }
    let time = u(6, 8)
    guard time <= UInt64(Int64.max) - UInt64(n) * 10000 else { throw CaptureError.packet }
    boot = UInt32(u(2, 4))
    uptime = time
    seq = UInt16(u(0, 2))
    rate = UInt16(hz)
    gap = p[16] & 2 != 0
    id = p[14]
    values = (0..<n).map { i in
      let j = 20 + i * stride
      if stride == 3 { return .green(UInt32(u(j, 3))) }
      func axis(_ k: Int) -> Int16 { Int16(bitPattern: UInt16(u(j + 2 * k, 2))) }
      return .acceleration(axis(0), axis(1), axis(2))
    }
  }
}
