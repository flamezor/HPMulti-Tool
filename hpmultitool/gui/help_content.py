"""Help pages (HTML) in English and German."""

from __future__ import annotations

HELP = {
    "en": [
        ("Overview", """
<h2>HPMulti-Tool</h2>
<p>Acquires, displays and exports readings from one or more HP / Agilent / Keysight 34401A
multimeters connected over RS-232.</p>
<ol>
<li><b>Instruments</b> (left): connected multimeters are found automatically. Tick the ones that
should measure.</li>
<li><b>Instrument settings</b> (middle): one tab per instrument – function, range, digits, math,
evaluation, trigger.</li>
<li><b>Measurement</b> (left): duration, interval, continuous measurement or measurement series
(loop). Then <i>Start measurement</i>.</li>
<li><b>Live readings</b> (right): large display, chart, table, summary, log.</li>
<li><b>Export</b>: save as CSV or TXT. Every run is also autosaved.</li>
</ol>
<p>Shortcuts: <b>F1</b> help, <b>F5</b> scan for instruments, <b>Enter</b> measure the next step of
a series.</p>"""),
        ("Connecting instruments", """
<h2>Connecting instruments</h2>
<ul>
<li>On the multimeter: <i>Shift › I/O MENU</i> → interface <b>RS-232</b>, <b>9600 baud</b>,
parity <b>Even (7 bits)</b>. These are the factory settings.</li>
<li>Cable: null-modem (e.g. a USB–RS232 null-modem adapter with FTDI chip).</li>
<li>Linux: the user must be in the <code>dialout</code> group.</li>
<li><i>Scan for instruments</i> (F5) probes every serial port. Ports without a USB ID (e.g. old
on-board COM ports) are only probed when that option is ticked.</li>
<li>Each instrument is shown with its <b>ID</b> (stored in the instrument), its port and the
serial number of the USB adapter. The ID – not the port – identifies the instrument, so it does
not matter which USB socket is used.</li>
<li>Before every measurement the tool checks that the expected instrument still answers on the
port.</li>
</ul>"""),
        ("Measurement functions", """
<h2>Measurement functions</h2>
<table cellpadding="4">
<tr><td><b>DC / AC voltage</b></td><td>100 mV … 1000 V (AC 750 V), AC as true RMS</td></tr>
<tr><td><b>DC / AC current</b></td><td>10 mA … 3 A, inputs I and LO</td></tr>
<tr><td><b>Resistance 2-wire</b></td><td>100 Ω … 100 MΩ, includes lead resistance</td></tr>
<tr><td><b>Resistance 4-wire</b></td><td>separate sense leads, eliminates lead resistance –
recommended below approx. 1 kΩ</td></tr>
<tr><td><b>Frequency / period</b></td><td>3 Hz … 300 kHz; the range is the input voltage
range</td></tr>
<tr><td><b>Voltage ratio</b></td><td>DC input / DC reference on the sense terminals</td></tr>
<tr><td><b>Continuity / diode</b></td><td>fixed ranges; usually used on the instrument
itself</td></tr>
</table>
<p><b>Without data logging:</b> <i>Switch instrument to this mode</i> configures the instrument and
returns it to its front panel – e.g. for continuity testing with the beeper.</p>
<p>The front/rear terminal switch and the continuity threshold cannot be set remotely; the tool
only shows the terminal setting.</p>"""),
        ("Range & resolution", """
<h2>Range & resolution (digits)</h2>
<p><b>Autorange</b> picks the range automatically (switches up at 120 %). A fixed range is faster
and avoids range changes during the measurement.</p>
<p><b>Digits</b> define how finely a reading is resolved. The ½ digit is a leading 0 or 1, so
“6½ digits” in the 100 Ω range means 100.0000 Ω.</p>
<table border="1" cellspacing="0" cellpadding="5">
<tr><th>Setting</th><th>Integration time</th><th>Example 108.64463 Ω</th><th>Speed</th></tr>
<tr><td>4½ digits fast</td><td>0.02 NPLC</td><td>108.64 Ω</td><td>very fast, noisy</td></tr>
<tr><td>4½ digits slow</td><td>1 NPLC</td><td>108.64 Ω</td><td>fast, suppresses mains hum</td></tr>
<tr><td>5½ digits fast</td><td>0.2 NPLC</td><td>108.645 Ω</td><td>fast</td></tr>
<tr><td>5½ digits slow</td><td>10 NPLC</td><td>108.645 Ω</td><td>medium</td></tr>
<tr><td>6½ digits fast</td><td>10 NPLC</td><td>108.6446 Ω</td><td>medium (default)</td></tr>
<tr><td>6½ digits slow</td><td>100 NPLC</td><td>108.6446 Ω</td><td>slow (≈ 4 s), lowest
noise</td></tr>
</table>
<p>NPLC = number of power-line cycles the input is integrated over (1 NPLC = 20 ms at 50 Hz).
Integer NPLC values suppress mains interference. The drop-down list and the preview below it show
what a reading will look like; once readings arrive, the preview uses the last real value. Live
display, table and export follow the selected digits; the CSV additionally contains the complete
raw value from the instrument.</p>
<p>For AC functions the digits only change the reported resolution; for frequency/period the gate
time sets the resolution (10 ms = 4½, 100 ms = 5½, 1 s = 6½ digits).</p>
<p><b>Autozero</b> measures the internal offset before every reading (more accurate, about twice
as slow). <b>Input resistance &gt;10 GΩ</b> loads high-impedance sources less (DC ranges up to
10 V).</p>"""),
        ("Math in the instrument", """
<h2>Math function (in the instrument)</h2>
<p>Calculated inside the 34401A; the instrument returns the result instead of the raw reading.
Only the combinations the instrument supports are offered.</p>
<ul>
<li><b>Null</b>: subtracts an offset – the first reading or a fixed value (e.g. lead
resistance).</li>
<li><b>Min / max / average</b>: the instrument keeps statistics; they are read at the end and
written to the TXT report.</li>
<li><b>dB / dBm</b>: voltage relative to a reference / as power into a reference resistance.</li>
<li><b>Limit test</b>: the instrument flags readings outside the limits (display HI/LO, beeper);
the tool marks them as BELOW/ABOVE LIMIT.</li>
</ul>"""),
        ("Evaluation on the PC", """
<h2>Evaluation (on the PC)</h2>
<p>Calculated by the tool for every reading. The original reading is always kept and exported as
well.</p>
<ul>
<li><b>Linear conversion</b> y = factor · x + offset with your own unit, e.g. a 4–20 mA pressure
transmitter: factor 625, offset −2.5, unit bar.</li>
<li><b>Per length</b>: resistance ÷ cable length → Ω/m, useful for cable tests.</li>
<li><b>Pt100 / Pt1000</b>: temperature in °C from a resistance reading (IEC 60751).</li>
<li><b>Tolerance check</b>: nominal ± % or ± absolute, or a min…max range. Every reading gets
PASS/FAIL; the summary shows the result per object. With a conversion, the tolerance applies to
the converted value.</li>
<li><b>Moving average</b>: an additional smoothed line in the chart.</li>
<li><b>Statistics</b> (always): minimum, maximum, mean, standard deviation σ, peak-to-peak and
drift per minute (slope of a linear fit).</li>
</ul>"""),
        ("Trigger & averaging", """
<h2>Trigger & averaging</h2>
<p><b>Trigger</b> = what starts a reading:</p>
<ul>
<li><b>Internal</b> (normal case): the tool requests a reading at every interval.</li>
<li><b>External</b>: every reading waits for a pulse on the <i>Ext Trig</i> jack on the rear
panel, e.g. from a test fixture or a PLC. The interval only sets the earliest next reading.</li>
<li><b>Software (*TRG)</b>: the tool sends a trigger command; behaves like internal.</li>
</ul>
<p><b>Trigger delay</b> = waiting time between the trigger and the reading so the signal can
settle (e.g. after a range change or with long cables). <i>Automatic</i> uses the values from the
manual depending on function, range and filter.</p>
<p><b>Averaging</b> = readings per point: the instrument measures N times in a row and the tool
stores the mean. Reduces noise by about √N, takes N times as long.</p>"""),
        ("Measurement & series (loop)", """
<h2>Measurement & measurement series (loop)</h2>
<p><b>Continuous measurement</b>: all ticked instruments measure together on a common time grid
for the selected duration (or until <i>Stop</i>) at the selected interval. <i>1 reading</i> takes
exactly one reading.</p>
<p><b>Measurement series (loop)</b>: measures several objects one after another, e.g. the cores of
a sensor cable:</p>
<ol>
<li>Choose <i>Measurement series</i> as mode and enter the objects (e.g. red, yellow, black,
white …) or insert a template. Drag to reorder.</li>
<li>Set the duration per object (often <i>1 reading</i> or a few seconds).</li>
<li><i>Start measurement</i>: a banner shows which object to connect to which instrument. Connect
it and press <b>Measure</b> (or Enter).</li>
<li>With two instruments, two objects are measured per step (e.g. T034 → red, T049 →
yellow).</li>
<li><i>Repeat last step</i> measures the previous object again (e.g. after a bad contact),
<i>Skip</i> leaves an object out, <i>End series</i> finishes early.</li>
<li>Alternatively <i>Automatically after a pause</i>: the next step starts after the pause.</li>
</ol>
<p>The <b>Summary</b> tab lists one line per object with mean, min, max, σ and PASS/FAIL. The TXT
report starts with the same table.</p>
<h3>Measure until stable</h3>
<p>Instead of a fixed duration, each instrument measures until its readings have settled: the
spread (max − min) of the last N readings must be within a limit, either in % of the reading or
as an absolute value. The duration then acts as the maximum time. The mean of the last N readings
is the <b>final value</b>; with a tolerance check only the final value is judged, and a
measurement that never became stable counts as FAIL. Typical use: temperature tests, long cables,
sensors that need time to settle.</p>
<p>Example: N = 10, limit 0.01 % at 1 reading per second → stable as soon as ten consecutive
readings of a 100 Ω conductor differ by less than 10 mΩ.</p>"""),
        ("Live mode", """
<h2>Live mode</h2>
<p>Switch to <b>Live</b> in the header. <i>Start live</i> keeps the ticked instruments connected and
shows their readings continuously – like the instrument's own display, but on the PC.</p>
<ul>
<li><b>Keys</b> for function, range and resolution work like the front panel; the instrument is
reconfigured immediately. The line above the reading shows the active settings (e.g. Ω4W · AUTO ·
6½ Digits · 10 NPLC · NULL).</li>
<li><b>Null</b> takes the next reading as offset (e.g. to subtract the lead resistance),
<b>Autozero</b> and <b>Hi-Z</b> are available where the function supports them.</li>
<li><b>MIN / MAX / Ø</b> run from the last change or <i>Reset</i>.</li>
<li><b>Pause</b> stops reading one instrument without disconnecting it.</li>
<li><b>Read rate</b>: how often a reading is taken; <i>As fast as possible</i> depends on the
resolution.</li>
<li><b>Record</b> logs the readings at any time (autosave included). After <i>Stop recording</i>
the data is available under Measurement › Export (CSV/TXT) and as PNG. A change of settings
during the recording starts a new section in the report.</li>
<li>Changes made in live mode are taken over into the instrument settings, so a following
measurement uses them.</li>
<li><i>Stop live</i> (or switching back to Measurement) returns the instruments to their front
panel.</li>
</ul>"""),
        ("Test profiles", """
<h2>Test profiles</h2>
<p>A test profile stores a complete setup under a name: mode, duration, interval, object list,
“until stable” settings, CSV format and the settings of every instrument (function, range,
digits, math, evaluation, trigger).</p>
<ul>
<li><b>Save …</b> stores the current setup (an existing name is overwritten after
confirmation).</li>
<li><b>Load</b> applies the selected profile. Instrument settings go to the instrument with the
same ID; if it is not connected, the settings are given to the remaining instruments in
order.</li>
<li>The active profile name is written to the TXT report.</li>
<li>Profiles are JSON files in the profile folder (📁) and can be copied to other computers.</li>
</ul>"""),
        ("Export & files", """
<h2>Export & files</h2>
<ul>
<li><b>CSV</b>: one line per reading – date, time, step, point, ID, label, port, function, range,
resolution, reading (rounded to the digits), unit, optionally calculated value and verdict,
status and raw value. Format: German (semicolon, decimal comma – opens directly in German Excel)
or international.</li>
<li><b>TXT</b>: readable report with all settings, statistics, summary and all readings.</li>
<li><b>Chart as PNG</b>: saves the current chart (all instruments, time of day on the x axis) as
an image in double screen resolution.</li>
<li><b>Autosave</b>: every measurement is written continuously to a CSV file in the autosave
folder, so no data is lost if the program or the PC crashes.</li>
</ul>
<p>Status values: OK, OVERLOAD (input outside the range, e.g. an open conductor), BELOW/ABOVE
LIMIT, TIMEOUT (no answer).</p>"""),
        ("Instrument ID & advanced", """
<h2>Instrument ID & advanced settings (⚙)</h2>
<p>The 34401A does not report a serial number. The tool uses the <b>calibration message</b>
(CAL:STRing, up to 40 characters, the display shows 12) as a unique ID, e.g. an asset number like
T034.</p>
<p>Writing a new ID: a JSON backup of the old message is saved first, calibration security is
disabled with the security code (factory default HP034401), the ID is written and read back, and
calibration security is enabled again. Calibration constants and the calibration count are not
changed.</p>
<p>Also available: self-test, error queue, reset (*RST), beeper test and text on the instrument
display.</p>"""),
        ("Troubleshooting", """
<h2>Troubleshooting</h2>
<ul>
<li><b>No instrument found</b>: instrument on? Interface RS-232, 9600 baud, even parity? Null-modem
cable? On Linux: <code>groups</code> must contain <code>dialout</code>.</li>
<li><b>“instrument not ready (DSR low)”</b>: the instrument is off, set to HP-IB, or the cable is
not a null-modem cable.</li>
<li><b>Same ID on two instruments</b>: assign unique IDs under ⚙ before measuring with both.</li>
<li><b>Interval not met</b>: a reading takes longer than the interval (high NPLC, autorange, slow
AC filter, averaging). Points are then skipped; the log shows a warning.</li>
<li><b>Instrument stays in remote mode</b> after a crash: press <i>LOCAL</i> (Shift) on the
instrument.</li>
</ul>"""),
    ],
    "de": [
        ("Überblick", """
<h2>HPMulti-Tool</h2>
<p>Erfasst, zeigt und exportiert Messwerte von einem oder mehreren Multimetern HP / Agilent /
Keysight 34401A über RS-232.</p>
<ol>
<li><b>Geräte</b> (links): angeschlossene Multimeter werden automatisch gefunden. Mit dem Haken
wählen, welche messen.</li>
<li><b>Geräteeinstellungen</b> (Mitte): ein Reiter pro Gerät – Funktion, Bereich, Digits, Math,
Auswertung, Trigger.</li>
<li><b>Messablauf</b> (links): Dauer, Intervall, fortlaufende Messung oder Messreihe (Loop). Dann
<i>Messung starten</i>.</li>
<li><b>Live-Messwerte</b> (rechts): große Anzeige, Diagramm, Tabelle, Übersicht, Protokoll.</li>
<li><b>Export</b>: als CSV oder TXT speichern. Jede Messung wird zusätzlich automatisch
gesichert.</li>
</ol>
<p>Tastenkürzel: <b>F1</b> Hilfe, <b>F5</b> Geräte suchen, <b>Enter</b> nächsten Schritt einer
Messreihe messen.</p>"""),
        ("Geräte anschließen", """
<h2>Geräte anschließen</h2>
<ul>
<li>Am Multimeter: <i>Shift › I/O MENU</i> → Schnittstelle <b>RS-232</b>, <b>9600 Baud</b>,
Parität <b>Even (7 Bit)</b>. Das ist die Werkseinstellung.</li>
<li>Kabel: Nullmodem (z. B. USB-RS232-Nullmodem-Adapter mit FTDI-Chip).</li>
<li>Linux: Der Benutzer muss in der Gruppe <code>dialout</code> sein.</li>
<li><i>Geräte suchen</i> (F5) prüft alle seriellen Ports. Ports ohne USB-Kennung (z. B. alte
COM-Ports auf dem Mainboard) nur, wenn die Option angehakt ist.</li>
<li>Jedes Gerät erscheint mit seiner <b>Kennung</b> (im Gerät gespeichert), dem Port und der
Seriennummer des USB-Adapters. Die Kennung – nicht der Port – identifiziert das Gerät; welche
USB-Buchse benutzt wird, ist egal.</li>
<li>Vor jeder Messung prüft das Tool, ob am Port noch das erwartete Gerät antwortet.</li>
</ul>"""),
        ("Messfunktionen", """
<h2>Messfunktionen</h2>
<table cellpadding="4">
<tr><td><b>Gleich-/Wechselspannung</b></td><td>100 mV … 1000 V (AC 750 V), AC als
Echt-Effektivwert</td></tr>
<tr><td><b>Gleich-/Wechselstrom</b></td><td>10 mA … 3 A, Eingänge I und LO</td></tr>
<tr><td><b>Widerstand 2-Leiter</b></td><td>100 Ω … 100 MΩ, enthält den
Leitungswiderstand</td></tr>
<tr><td><b>Widerstand 4-Leiter</b></td><td>getrennte Sense-Leitungen, eliminiert den
Leitungswiderstand – empfohlen unter ca. 1 kΩ</td></tr>
<tr><td><b>Frequenz / Periode</b></td><td>3 Hz … 300 kHz; der Bereich ist der
Eingangsspannungsbereich</td></tr>
<tr><td><b>Spannungsverhältnis</b></td><td>DC-Eingang / DC-Referenz an den
Sense-Buchsen</td></tr>
<tr><td><b>Durchgang / Diode</b></td><td>feste Bereiche; meist direkt am Gerät genutzt</td></tr>
</table>
<p><b>Ohne Messwerterfassung:</b> <i>Gerät in diesen Modus schalten</i> konfiguriert das Gerät und
gibt es an die Frontplatte zurück – z. B. für die Durchgangsprüfung mit Piepton.</p>
<p>Front/Rear-Umschalter und Durchgangs-Schwelle sind nicht fernsteuerbar; der Umschalter wird nur
angezeigt.</p>"""),
        ("Bereich & Auflösung", """
<h2>Bereich & Auflösung (Digits)</h2>
<p><b>Autorange</b> wählt den Bereich automatisch (schaltet bei 120 % hoch). Ein fester Bereich ist
schneller und verhindert Bereichswechsel während der Messung.</p>
<p><b>Digits</b> legen fest, wie fein ein Messwert aufgelöst wird. Die ½ Stelle ist eine führende
0 oder 1 – „6½ Digits“ im 100-Ω-Bereich heißt also 100,0000 Ω.</p>
<table border="1" cellspacing="0" cellpadding="5">
<tr><th>Einstellung</th><th>Integrationszeit</th><th>Beispiel 108,64463 Ω</th><th>Tempo</th></tr>
<tr><td>4½ Digits schnell</td><td>0,02 NPLC</td><td>108,64 Ω</td><td>sehr schnell,
verrauscht</td></tr>
<tr><td>4½ Digits langsam</td><td>1 NPLC</td><td>108,64 Ω</td><td>schnell, unterdrückt
Netzbrumm</td></tr>
<tr><td>5½ Digits schnell</td><td>0,2 NPLC</td><td>108,645 Ω</td><td>schnell</td></tr>
<tr><td>5½ Digits langsam</td><td>10 NPLC</td><td>108,645 Ω</td><td>mittel</td></tr>
<tr><td>6½ Digits schnell</td><td>10 NPLC</td><td>108,6446 Ω</td><td>mittel (Standard)</td></tr>
<tr><td>6½ Digits langsam</td><td>100 NPLC</td><td>108,6446 Ω</td><td>langsam (≈ 4 s),
geringstes Rauschen</td></tr>
</table>
<p>NPLC = Anzahl der Netzperioden, über die integriert wird (1 NPLC = 20 ms bei 50 Hz).
Ganzzahlige NPLC unterdrücken Netzstörungen. Die Auswahlliste und die Vorschau darunter zeigen,
wie ein Messwert aussehen wird; sobald Messwerte kommen, nutzt die Vorschau den letzten echten
Wert. Live-Anzeige, Tabelle und Export folgen den gewählten Digits; die CSV enthält zusätzlich den
vollständigen Rohwert des Geräts.</p>
<p>Bei AC-Funktionen ändern die Digits nur die gemeldete Auflösung; bei Frequenz/Periode bestimmt
die Gate-Zeit die Auflösung (10 ms = 4½, 100 ms = 5½, 1 s = 6½ Digits).</p>
<p><b>Autozero</b> misst vor jeder Messung den internen Offset (genauer, etwa halb so schnell).
<b>Eingangswiderstand &gt;10 GΩ</b> belastet hochohmige Quellen weniger (DC-Bereiche bis
10 V).</p>"""),
        ("Math-Funktion im Gerät", """
<h2>Math-Funktion (im Gerät)</h2>
<p>Wird im 34401A gerechnet; das Gerät liefert statt des Rohwerts das Ergebnis. Angeboten werden
nur die Kombinationen, die das Gerät unterstützt.</p>
<ul>
<li><b>Null</b>: zieht einen Offset ab – den ersten Messwert oder einen festen Wert (z. B. den
Leitungswiderstand).</li>
<li><b>Min / Max / Mittelwert</b>: das Gerät führt eine Statistik; sie wird am Ende gelesen und im
TXT-Protokoll ausgegeben.</li>
<li><b>dB / dBm</b>: Spannung relativ zu einer Referenz bzw. als Leistung an einem
Referenzwiderstand.</li>
<li><b>Grenzwerttest</b>: das Gerät markiert Werte außerhalb der Grenzen (Anzeige HI/LO,
Piepton); das Tool kennzeichnet sie als UNTER/ÜBER GRENZE.</li>
</ul>"""),
        ("Auswertung am PC", """
<h2>Auswertung (am PC)</h2>
<p>Wird vom Tool für jeden Messwert berechnet. Der Originalmesswert bleibt immer erhalten und wird
mit exportiert.</p>
<ul>
<li><b>Lineare Umrechnung</b> y = Faktor · x + Offset mit eigener Einheit, z. B. ein
4–20-mA-Drucksensor: Faktor 625, Offset −2,5, Einheit bar.</li>
<li><b>Pro Länge</b>: Widerstand ÷ Leitungslänge → Ω/m, praktisch für Kabelprüfungen.</li>
<li><b>Pt100 / Pt1000</b>: Temperatur in °C aus einer Widerstandsmessung (IEC 60751).</li>
<li><b>Toleranzprüfung</b>: Sollwert ± % oder ± absolut oder ein Bereich Min…Max. Jeder Messwert
bekommt i. O./n. i. O.; die Übersicht zeigt das Ergebnis je Objekt. Mit Umrechnung gilt die
Toleranz für den umgerechneten Wert.</li>
<li><b>Gleitender Mittelwert</b>: zusätzliche geglättete Linie im Diagramm.</li>
<li><b>Statistik</b> (immer): Minimum, Maximum, Mittelwert, Standardabweichung σ, Spannweite und
Drift pro Minute (Steigung einer Ausgleichsgeraden).</li>
</ul>"""),
        ("Trigger & Mittelung", """
<h2>Trigger & Mittelung</h2>
<p><b>Trigger</b> = was eine Messung auslöst:</p>
<ul>
<li><b>Intern</b> (Normalfall): das Tool fordert in jedem Intervall einen Messwert an.</li>
<li><b>Extern</b>: jede Messung wartet auf einen Impuls an der <i>Ext-Trig</i>-Buchse auf der
Rückseite, z. B. von einer Prüfvorrichtung oder SPS. Das Intervall bestimmt nur den frühesten
nächsten Messwert.</li>
<li><b>Software (*TRG)</b>: das Tool sendet einen Trigger-Befehl; verhält sich wie intern.</li>
</ul>
<p><b>Trigger-Verzögerung</b> = Wartezeit zwischen Trigger und Messung, damit sich das Signal
einschwingen kann (z. B. nach einem Bereichswechsel oder bei langen Leitungen). <i>Automatisch</i>
nutzt die Werte aus dem Handbuch passend zu Funktion, Bereich und Filter.</p>
<p><b>Mittelung</b> = Messungen je Messpunkt: das Gerät misst N-mal direkt hintereinander, das
Tool speichert den Mittelwert. Reduziert das Rauschen etwa um √N, dauert N-mal so lange.</p>"""),
        ("Messablauf & Messreihe (Loop)", """
<h2>Messablauf & Messreihe (Loop)</h2>
<p><b>Fortlaufende Messung</b>: alle angehakten Geräte messen gemeinsam auf einem Zeitraster für
die gewählte Dauer (oder bis <i>Stopp</i>) im gewählten Intervall. <i>1 Messwert</i> nimmt genau
einen Messwert auf.</p>
<p><b>Messreihe (Loop)</b>: misst mehrere Objekte nacheinander, z. B. die Adern eines
Sensorkabels:</p>
<ol>
<li>Betriebsart <i>Messreihe</i> wählen und die Objekte eintragen (z. B. rot, gelb, schwarz,
weiß …) oder eine Vorlage einfügen. Reihenfolge per Ziehen ändern.</li>
<li>Messdauer je Objekt einstellen (oft <i>1 Messwert</i> oder wenige Sekunden).</li>
<li><i>Messung starten</i>: ein Banner zeigt, welches Objekt an welches Gerät anzuschließen ist.
Anschließen und <b>Messen</b> drücken (oder Enter).</li>
<li>Mit zwei Geräten werden je Schritt zwei Objekte gemessen (z. B. T034 → rot, T049 →
gelb).</li>
<li><i>Letzten Schritt wiederholen</i> misst das vorige Objekt erneut (z. B. nach einem
Wackelkontakt), <i>Überspringen</i> lässt ein Objekt aus, <i>Messreihe beenden</i> bricht vorzeitig
ab.</li>
<li>Alternativ <i>Automatisch nach Pause</i>: der nächste Schritt startet nach Ablauf der
Pause.</li>
</ol>
<p>Der Reiter <b>Übersicht</b> zeigt je Objekt eine Zeile mit Mittelwert, Min, Max, σ und
i. O./n. i. O. Das TXT-Protokoll beginnt mit derselben Tabelle.</p>
<h3>Messen bis stabil</h3>
<p>Statt einer festen Dauer misst jedes Gerät, bis sich die Werte beruhigt haben: Die Spannweite
(Max − Min) der letzten N Messwerte muss innerhalb einer Grenze liegen – in % vom Messwert oder
absolut. Die Messdauer gilt dann als Höchstdauer. Der Mittelwert der letzten N Messwerte ist der
<b>Endwert</b>; bei einer Toleranzprüfung wird nur der Endwert bewertet, eine Messung, die nicht
stabil wurde, gilt als n. i. O. Typisch für Temperaturprüfungen, lange Leitungen und Sensoren mit
Einschwingzeit.</p>
<p>Beispiel: N = 10, Grenze 0,01 % bei 1 Messwert pro Sekunde → stabil, sobald zehn aufeinander
folgende Werte eines 100-Ω-Leiters weniger als 10 mΩ auseinanderliegen.</p>"""),
        ("Live-Modus", """
<h2>Live-Modus</h2>
<p>In der Kopfzeile auf <b>Live</b> umschalten. <i>Live starten</i> hält die angehakten Geräte
verbunden und zeigt ihre Messwerte fortlaufend – wie das Display am Gerät, nur am PC.</p>
<ul>
<li>Die <b>Tasten</b> für Funktion, Bereich und Auflösung funktionieren wie an der Frontplatte;
das Gerät wird sofort umgestellt. Die Zeile über dem Messwert zeigt die aktiven Einstellungen
(z. B. Ω4W · AUTO · 6½ Digits · 10 NPLC · NULL).</li>
<li><b>Null</b> übernimmt den nächsten Messwert als Offset (z. B. um den Leitungswiderstand
abzuziehen), <b>Autozero</b> und <b>Hi-Z</b> gibt es, wo die Funktion sie unterstützt.</li>
<li><b>MIN / MAX / Ø</b> laufen seit der letzten Änderung oder seit <i>Zurücksetzen</i>.</li>
<li><b>Pause</b> hält ein Gerät an, ohne die Verbindung zu trennen.</li>
<li><b>Leserate</b>: wie oft gemessen wird; <i>So schnell wie möglich</i> hängt von der Auflösung
ab.</li>
<li><b>Aufnahme</b> schreibt die Messwerte jederzeit mit (inklusive Autosave). Nach <i>Aufnahme
stoppen</i> stehen die Daten unter Messung › Export (CSV/TXT) und als PNG bereit. Eine Änderung der
Einstellungen während der Aufnahme beginnt einen neuen Abschnitt im Protokoll.</li>
<li>Änderungen im Live-Modus werden in die Geräteeinstellungen übernommen, eine folgende Messung
nutzt sie also.</li>
<li><i>Live beenden</i> (oder zurück zu Messung) gibt die Geräte an die Frontplatte zurück.</li>
</ul>"""),
        ("Prüfprofile", """
<h2>Prüfprofile</h2>
<p>Ein Prüfprofil speichert eine komplette Einrichtung unter einem Namen: Betriebsart, Dauer,
Intervall, Objektliste, „bis stabil“-Einstellungen, CSV-Format und die Einstellungen jedes Geräts
(Funktion, Bereich, Digits, Math, Auswertung, Trigger).</p>
<ul>
<li><b>Speichern …</b> sichert die aktuelle Einrichtung (ein vorhandener Name wird nach Rückfrage
überschrieben).</li>
<li><b>Laden</b> übernimmt das gewählte Profil. Geräteeinstellungen gehen an das Gerät mit
derselben Kennung; ist es nicht angeschlossen, werden die Einstellungen der Reihe nach auf die
übrigen Geräte verteilt.</li>
<li>Der Name des aktiven Profils steht im TXT-Protokoll.</li>
<li>Profile sind JSON-Dateien im Profilordner (📁) und lassen sich auf andere Rechner
kopieren.</li>
</ul>"""),
        ("Export & Dateien", """
<h2>Export & Dateien</h2>
<ul>
<li><b>CSV</b>: eine Zeile je Messwert – Datum, Uhrzeit, Schritt, Messpunkt, Kennung,
Bezeichnung, Port, Funktion, Bereich, Auflösung, Messwert (auf die Digits gerundet), Einheit,
optional berechneter Wert und Bewertung, Status und Rohwert. Format: Deutsch (Semikolon,
Dezimalkomma – öffnet direkt in deutschem Excel) oder international.</li>
<li><b>TXT</b>: lesbares Protokoll mit allen Einstellungen, Statistik, Übersicht und allen
Messwerten.</li>
<li><b>Diagramm als PNG</b>: speichert das aktuelle Diagramm (alle Geräte, Uhrzeit auf der
x-Achse) als Bild in doppelter Bildschirmauflösung.</li>
<li><b>Autosave</b>: jede Messung wird fortlaufend als CSV im Autosave-Ordner gespeichert – bei
einem Absturz von Programm oder PC gehen keine Daten verloren.</li>
</ul>
<p>Status: OK, OVERLOAD (Eingang außerhalb des Bereichs, z. B. offener Leiter), UNTER/ÜBER GRENZE,
TIMEOUT (keine Antwort).</p>"""),
        ("Gerätekennung & Erweitert", """
<h2>Gerätekennung & erweiterte Einstellungen (⚙)</h2>
<p>Der 34401A meldet keine Seriennummer. Das Tool nutzt die <b>Kalibriermeldung</b> (CAL:STRing,
bis 40 Zeichen, das Display zeigt 12) als eindeutige Kennung, z. B. eine Inventarnummer wie
T034.</p>
<p>Neue Kennung schreiben: zuerst wird eine JSON-Sicherung der alten Meldung angelegt, die
Kalibriersicherung mit dem Sicherheitscode aufgehoben (Werkseinstellung HP034401), die Kennung
geschrieben und zurückgelesen und die Kalibriersicherung wieder aktiviert. Kalibrierwerte und
Kalibrierzähler bleiben unverändert.</p>
<p>Außerdem: Selbsttest, Fehlerspeicher, Reset (*RST), Signalton-Test und Text auf dem
Gerätedisplay.</p>"""),
        ("Fehlerbehebung", """
<h2>Fehlerbehebung</h2>
<ul>
<li><b>Kein Gerät gefunden</b>: Gerät an? Schnittstelle RS-232, 9600 Baud, gerade Parität?
Nullmodemkabel? Unter Linux: <code>groups</code> muss <code>dialout</code> enthalten.</li>
<li><b>„Gerät nicht bereit (DSR inaktiv)“</b>: Gerät aus, auf HP-IB eingestellt oder kein
Nullmodemkabel.</li>
<li><b>Gleiche Kennung bei zwei Geräten</b>: vor dem gemeinsamen Messen unter ⚙ eindeutige
Kennungen vergeben.</li>
<li><b>Intervall wird nicht eingehalten</b>: eine Messung dauert länger als das Intervall (hohe
NPLC, Autorange, langsamer AC-Filter, Mittelung). Dann werden Zeitpunkte übersprungen; das
Protokoll zeigt eine Warnung.</li>
<li><b>Gerät bleibt im Remote-Modus</b> nach einem Absturz: am Gerät <i>LOCAL</i> (Shift)
drücken.</li>
</ul>"""),
    ],
}
