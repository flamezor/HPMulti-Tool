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
<tr><td><b>Continuity / diode</b></td><td>fixed ranges (1 kΩ / 1 V, 1 mA test current);
front-panel modes, not logged</td></tr>
</table>
<h3>Continuity and diode test</h3>
<p>Both are used directly on the instrument: it compares each reading with its own threshold
and beeps – continuity below the threshold (factory setting 10 Ω, adjustable from 1 to 1000 Ω
only on the front panel: Shift › Menu Recall › 2: CONTINUITY), diode test at 0.3 … 0.8 V. The
continuity tone cannot be switched off.</p>
<ul>
<li><i>Switch instrument to this mode</i> (settings, card <i>Without data logging</i>) configures
the instrument and returns it to its front panel – the normal way to test with the beeper.</li>
<li>In the <b>live mode</b> (keys CONT and DIODE) the readings can also be watched on the PC.</li>
<li>The measurement plan does not log them: the tool cannot read the threshold, so the readings
alone say nothing about pass or fail. To document resistances, e.g. the cores of a cable, use
<i>resistance 2-wire</i> or <i>4-wire</i> – with selectable range, 6½ digits and a measurement
uncertainty.</li>
</ul>
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
<p>Every measurement scatters a little: noise, contact resistance and the instrument itself make
each reading slightly different. A single reading therefore says little about how exact it is.
For every series of readings (per instrument and measured object) the tool calculates the
<b>measurement result</b> – the best value <i>and</i> how reliable it is:</p>
<p align="center" style="font-size:13pt"><b>x̄ ± u</b> &nbsp; e.g. &nbsp;
<b>(5.00220 ± 0.00031) V</b> &nbsp; (68.3 %)</p>
<p>Read as: the best value is 5.00220 V; the true value lies between 5.00189 V and 5.00251 V with
a probability of about 68 %. The original readings are always kept and exported as well.</p>

<h3>Step by step</h3>
<p>The example uses five readings of a DC voltage in the 10 V range:
5.0021 · 5.0023 · 5.0022 · 5.0024 · 5.0020 V.</p>
<table border="1" cellspacing="0" cellpadding="6">
<tr><th>Quantity</th><th>Formula</th><th>What it tells you</th><th>Example</th></tr>
<tr><td><b>Mean</b> x̄</td><td>x̄ = (x<sub>1</sub> + x<sub>2</sub> + … + x<sub>n</sub>) / n</td>
<td>The best estimate of the true value. Random deviations up and down cancel out.</td>
<td>5.0022 V</td></tr>
<tr><td><b>Standard deviation</b> s</td>
<td>s = √( Σ (x<sub>i</sub> − x̄)² / (n − 1) )</td>
<td>How much a <i>single</i> reading scatters around the mean. It hardly changes with more
readings – it describes the measurement setup.</td><td>0.16 mV</td></tr>
<tr><td><b>Standard deviation of the mean</b> s(x̄)</td><td>s(x̄) = s / √n</td>
<td>How exactly the <i>mean</i> is known. It decreases with more readings: four times as many
readings halve it.</td><td>0.071 mV</td></tr>
<tr><td><b>Student factor</b> t</td><td>from the t-distribution for n − 1 degrees of freedom
and the confidence level</td>
<td>Short series estimate the scatter less reliably. t widens the interval to make up for it;
for many readings t approaches 1 (68.3 %) or 2 (95 %).</td><td>1.14 (n = 5, 68.3 %)</td></tr>
<tr><td><b>Random part</b></td><td>t · s(x̄)</td>
<td>The part of the uncertainty caused by the scatter of the readings.</td><td>0.081 mV</td></tr>
<tr><td><b>Instrument error</b> h</td><td>h = (% of reading · |x̄| + % of range · range) / 100</td>
<td>How far the multimeter itself may be off, according to its data sheet. The scatter cannot
reveal this error – every reading is off in the same way.</td>
<td>0.0035 % · 5 V + 0.0005 % · 10 V = 0.23 mV</td></tr>
<tr><td><b>Uncertainty</b> u</td><td>u = t · s(x̄) + h</td>
<td>Both parts added: the range in which the true value lies.</td><td>0.31 mV</td></tr>
<tr><td><b>Relative uncertainty</b></td><td>u / |x̄| · 100 %</td>
<td>The uncertainty in percent of the result – handy for comparing measurements.</td>
<td>0.0061 %</td></tr>
</table>

<h3>Rounding</h3>
<p>u is rounded to <b>two significant digits</b>, and x̄ is rounded to the same decimal place.
More digits would only pretend an accuracy that does not exist. Example: (83.62 ± 2.624) Ω becomes
<b>(83.6 ± 2.6) Ω</b>. A 5 in the last place is rounded to the even digit (4.135 → 4.14,
4.125 → 4.12), so rounding up and down even out.</p>

<h3>Confidence level</h3>
<p>The confidence level states how probable it is that the true value lies within x̄ ± u. Choose it
per instrument under <i>Evaluation (on the PC)</i>:</p>
<table border="1" cellspacing="0" cellpadding="5">
<tr><th>Level</th><th>Typical use</th><th>t for n = 4 / 5 / 10 / 30 / 100</th></tr>
<tr><td>68.3 % (1 σ)</td><td>physics lab courses, quick comparisons</td>
<td>1.20 / 1.14 / 1.06 / 1.02 / 1.01</td></tr>
<tr><td>95 %</td><td>test reports, calibration certificates, industry</td>
<td>3.18 / 2.78 / 2.26 / 2.05 / 1.98</td></tr>
<tr><td>99 %</td><td>safety-relevant statements</td><td>5.84 / 4.60 / 3.25 / 2.76 / 2.63</td></tr>
</table>
<p>A higher level makes the interval wider (95 % in the example: (5.00220 ± 0.00042) V). It does
not make the measurement better – it only makes the statement more certain.</p>

<h3>Instrument error h</h3>
<p>The values come from the accuracy tables of the 34401A user's guide (chapter 8). They depend on
the function, the range and the reading, and on the <b>time since the last calibration</b>
(24 hours, 90 days or 1 year – select this per instrument). The settings are taken into account:</p>
<ul>
<li>less than 6½ digits: additional noise error;</li>
<li>2-wire resistance without null: +0.2 Ω for the test leads;</li>
<li>autozero off: small additional error;</li>
<li>AC voltage and current: the error depends on the <b>signal frequency</b> (enter it, default
50 Hz) and on the AC filter; signals below 5 % of the range get an additional error;</li>
<li>frequency and period: the error depends on the gate time.</li>
</ul>
<p>The field below the settings shows h for the last (or an example) reading, with the reasons.</p>
<p><b>Which time since calibration?</b> The data sheet gives every accuracy in three columns. The
instrument drifts slowly after its calibration, so the permitted error grows with time:</p>
<table>
<tr><th>Setting</th><th>Meaning</th></tr>
<tr><td>24 hours (23 °C ± 1 °C)</td><td>directly after calibration, in a temperature-controlled
lab – only for special cases</td></tr>
<tr><td>90 days (23 °C ± 5 °C)</td><td>calibrated within the last three months</td></tr>
<tr><td>1 year (23 °C ± 5 °C)</td><td><b>normal case</b>: instrument with a yearly
calibration</td></tr>
</table>
<p>Example 1 kΩ range, 1 year: ± (0.010 % of the reading + 0.001 % of the range); at 108.6446 Ω
that is 10.9 mΩ + 10 mΩ ≈ <b>21 mΩ</b>. The tool does not know the calibration date of the
instrument – choose the column that matches your calibration interval.</p>
<p><b>Limits:</b> the data sheet applies at 18 … 28 °C after one hour of warm-up. With autorange the
smallest range that holds the value is assumed (on the safe side). For dB/dBm and the voltage
ratio the data sheet gives no simple value; u then contains only the random part and a note says
so.</p>

<h3>How many readings?</h3>
<p>A standard deviation needs at least <b>4 readings</b>. With fewer readings the result is marked
<i>not valid</i>, and u contains only the instrument error h (as for a single reading). The plan
summary warns before the start when a measurement will deliver fewer than 4 readings.</p>
<p>More readings make the random part smaller, but never h. Once t · s(x̄) is small compared with
h, further readings hardly improve the result – in the example h dominates already with five
readings. Readings with overload or errors are not used and are counted separately.</p>

<h3>Conversion</h3>
<ul>
<li><b>Linear</b>: y = factor · x + offset with your own unit, e.g. a 4–20 mA pressure
transmitter for 0–10 bar: factor 625, offset −2.5, unit bar.</li>
<li><b>Per length</b>: reading ÷ cable length, e.g. Ω/m for cable tests.</li>
</ul>
<p>The result is converted as well, and u is multiplied by the factor:
(12.000 ± 0.019) mA → (5.000 ± 0.012) bar. The uncertainty of the sensor or of the cable length
is not known to the tool and is not included.</p>

<h3>Where to find it</h3>
<ul>
<li><b>Readout tile</b>: x̄ ± u while measuring, plus s, h, min, max and n.</li>
<li><b>Overview</b> tab: one line per instrument and object with all intermediate values.</li>
<li><b>TXT report</b>: the complete calculation for every instrument, including the notes.</li>
</ul>

<h3>Without measurement uncertainty</h3>
<p>If only the readings and their statistics are of interest, switch off <i>Calculate measurement
uncertainty</i>. Then only the mean x̄, the standard deviation s, s(x̄), minimum and maximum are
calculated; t, h and u are left out of the tile, the overview and the export, and the warning
about too few readings disappears. Conversion still works.</p>"""),
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
white …), one per line in the order of measurement – or choose a template. Your own lists can be
kept with <i>Save as template …</i>: choose a template, change the list and save it under the same
name to edit it. <i>Delete template</i> removes it; deleted standard templates come back with
<i>Restore standard templates</i>.</li>
<li>Set the duration per object (often <i>1 reading</i> or a few seconds).</li>
<li><i>Start measurement</i>: a banner shows which object to connect to which instrument. Connect
it and press <b>Measure</b> (or Enter).</li>
<li>With two instruments, each one has its own list: choose under <i>Edit the list of</i> which
instrument's list is shown. In every step each instrument measures its next object (e.g. T034 →
red, T049 → white). An instrument with a shorter list rests in the last steps; one without
objects is not measured.</li>
<li><i>Repeat last step</i> measures the previous object again (e.g. after a bad contact),
<i>Skip</i> leaves an object out, <i>End series</i> finishes early.</li>
<li>Alternatively <i>Automatically after a pause</i>: the next step starts after the pause.</li>
</ol>
<p>The <b>Overview</b> tab lists one line per object with n, x̄, s, s(x̄), t, h, u and the result
x̄ ± u. The TXT report starts with the same table.</p>
<h3>Measure until stable</h3>
<p>Instead of a fixed duration, each instrument measures until its readings have settled: the
spread (max − min) of the last N readings must be within a limit, either in % of the reading or
as an absolute value. The duration then acts as the maximum time. The mean of the last N readings
is the <b>final value</b>. Typical use: temperature tests, long cables, sensors that need time to
settle.</p>
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
<li><b>MIN / MAX / Ø</b> run from the last change or <i>Reset</i>. <i>Reset</i> also clears
the chart of that instrument (a running recording keeps all readings).</li>
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
resolution, reading (rounded to the digits), unit, optionally calculated value, status and raw
value. Format: German (semicolon, decimal comma – opens directly in German Excel)
or international.</li>
<li><b>TXT</b>: readable report with all settings, the measurement result x̄ ± u with all
intermediate values, summary and all readings.</li>
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
<p>Also available: self-test, error queue, reset (*RST) and beeper test.</p>"""),
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
<tr><td><b>Durchgang / Diode</b></td><td>feste Bereiche (1 kΩ / 1 V, Prüfstrom 1 mA);
Modi für die Frontplatte, werden nicht protokolliert</td></tr>
</table>
<h3>Durchgangsprüfung und Diodentest</h3>
<p>Beide werden direkt am Gerät genutzt: Es vergleicht jeden Messwert mit seiner eigenen Schwelle
und piept – bei Durchgang unterhalb der Schwelle (ab Werk 10 Ω, einstellbar von 1 bis 1000 Ω nur an
der Frontplatte: Shift › Menu Recall › 2: CONTINUITY), beim Diodentest bei 0,3 … 0,8 V. Der
Durchgangston lässt sich nicht abschalten.</p>
<ul>
<li><i>Gerät in diesen Modus schalten</i> (Einstellungen, Karte <i>Ohne Messwerterfassung</i>)
konfiguriert das Gerät und gibt es an die Frontplatte zurück – der normale Weg für die Prüfung
mit Piepton.</li>
<li>Im <b>Live-Modus</b> (Tasten CONT und DIODE) lassen sich die Messwerte zusätzlich am PC
verfolgen.</li>
<li>Im Messablauf werden sie nicht protokolliert: Das Tool kann die Schwelle nicht auslesen, die
Messwerte allein sagen also nichts über Durchgang ja/nein. Um Widerstände zu dokumentieren, z. B.
die Adern eines Kabels, <i>Widerstand 2-Leiter</i> oder <i>4-Leiter</i> verwenden – mit wählbarem
Bereich, 6½ Digits und Messunsicherheit.</li>
</ul>
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
<p>Jede Messung streut ein wenig: Rauschen, Übergangswiderstände und das Messgerät selbst sorgen
dafür, dass jeder Messwert etwas anders ausfällt. Ein einzelner Messwert sagt deshalb wenig darüber
aus, wie genau er ist. Für jede Messreihe (je Gerät und Messobjekt) berechnet das Tool daher das
<b>Messergebnis</b> – den besten Wert <i>und</i> wie verlässlich er ist:</p>
<p align="center" style="font-size:13pt"><b>x̄ ± u</b> &nbsp; z. B. &nbsp;
<b>(5,00220 ± 0,00031) V</b> &nbsp; (68,3 %)</p>
<p>Gelesen: Der beste Wert ist 5,00220 V; der wahre Wert liegt mit etwa 68 % Wahrscheinlichkeit
zwischen 5,00189 V und 5,00251 V. Die Originalmesswerte bleiben immer erhalten und werden mit
exportiert.</p>

<h3>Schritt für Schritt</h3>
<p>Das Beispiel verwendet fünf Messwerte einer Gleichspannung im 10-V-Bereich:
5,0021 · 5,0023 · 5,0022 · 5,0024 · 5,0020 V.</p>
<table border="1" cellspacing="0" cellpadding="6">
<tr><th>Größe</th><th>Formel</th><th>Was sie aussagt</th><th>Beispiel</th></tr>
<tr><td><b>Mittelwert</b> x̄</td><td>x̄ = (x<sub>1</sub> + x<sub>2</sub> + … + x<sub>n</sub>) / n</td>
<td>Der beste Schätzwert für den wahren Wert. Zufällige Abweichungen nach oben und unten heben
sich auf.</td><td>5,0022 V</td></tr>
<tr><td><b>Standardabweichung</b> s</td>
<td>s = √( Σ (x<sub>i</sub> − x̄)² / (n − 1) )</td>
<td>Wie stark ein <i>einzelner</i> Messwert um den Mittelwert streut. Sie ändert sich mit mehr
Messwerten kaum – sie beschreibt den Messaufbau.</td><td>0,16 mV</td></tr>
<tr><td><b>Standardabweichung des Mittelwerts</b> s(x̄)</td><td>s(x̄) = s / √n</td>
<td>Wie genau der <i>Mittelwert</i> bekannt ist. Sie sinkt mit mehr Messwerten: viermal so viele
Messwerte halbieren sie.</td><td>0,071 mV</td></tr>
<tr><td><b>Student-Faktor</b> t</td><td>aus der t-Verteilung für n − 1 Freiheitsgrade und das
Vertrauensniveau</td>
<td>Kurze Messreihen schätzen die Streuung unsicherer. t vergrößert das Intervall als Ausgleich;
bei vielen Messwerten geht t gegen 1 (68,3 %) bzw. 2 (95 %).</td><td>1,14 (n = 5, 68,3 %)</td></tr>
<tr><td><b>Zufälliger Anteil</b></td><td>t · s(x̄)</td>
<td>Der Teil der Unsicherheit, der von der Streuung der Messwerte kommt.</td><td>0,081 mV</td></tr>
<tr><td><b>Gerätefehler</b> h</td><td>h = (% vom Messwert · |x̄| + % vom Bereich · Bereich) / 100</td>
<td>Wie weit das Multimeter selbst laut Datenblatt danebenliegen darf. Die Streuung kann diesen
Fehler nicht zeigen – jeder Messwert ist gleichermaßen betroffen.</td>
<td>0,0035 % · 5 V + 0,0005 % · 10 V = 0,23 mV</td></tr>
<tr><td><b>Messunsicherheit</b> u</td><td>u = t · s(x̄) + h</td>
<td>Beide Anteile zusammen: der Bereich, in dem der wahre Wert liegt.</td><td>0,31 mV</td></tr>
<tr><td><b>Relative Unsicherheit</b></td><td>u / |x̄| · 100 %</td>
<td>Die Unsicherheit in Prozent vom Ergebnis – praktisch, um Messungen zu vergleichen.</td>
<td>0,0061 %</td></tr>
</table>

<h3>Rundung</h3>
<p>u wird auf <b>zwei signifikante Stellen</b> gerundet und x̄ auf dieselbe Dezimalstelle. Mehr
Stellen würden nur eine Genauigkeit vortäuschen, die es nicht gibt. Beispiel: aus
(83,62 ± 2,624) Ω wird <b>(83,6 ± 2,6) Ω</b>. Eine 5 an der letzten Stelle wird auf die gerade
Ziffer gerundet (4,135 → 4,14; 4,125 → 4,12), damit sich Auf- und Abrunden ausgleichen.</p>

<h3>Vertrauensniveau</h3>
<p>Das Vertrauensniveau gibt an, wie wahrscheinlich der wahre Wert innerhalb von x̄ ± u liegt.
Es wird je Gerät unter <i>Auswertung (am PC)</i> gewählt:</p>
<table border="1" cellspacing="0" cellpadding="5">
<tr><th>Niveau</th><th>Typischer Einsatz</th><th>t bei n = 4 / 5 / 10 / 30 / 100</th></tr>
<tr><td>68,3 % (1 σ)</td><td>Physik-Praktikum, schnelle Vergleiche</td>
<td>1,20 / 1,14 / 1,06 / 1,02 / 1,01</td></tr>
<tr><td>95 %</td><td>Prüfberichte, Kalibrierscheine, Industrie</td>
<td>3,18 / 2,78 / 2,26 / 2,05 / 1,98</td></tr>
<tr><td>99 %</td><td>sicherheitsrelevante Aussagen</td><td>5,84 / 4,60 / 3,25 / 2,76 / 2,63</td></tr>
</table>
<p>Ein höheres Niveau macht das Intervall breiter (95 % im Beispiel: (5,00220 ± 0,00042) V). Die
Messung wird dadurch nicht besser – nur die Aussage sicherer.</p>

<h3>Gerätefehler h</h3>
<p>Die Werte stammen aus den Genauigkeitstabellen im Handbuch des 34401A (Kapitel 8). Sie hängen
von Funktion, Bereich und Messwert ab sowie von der <b>Zeit seit der letzten Kalibrierung</b>
(24 Stunden, 90 Tage oder 1 Jahr – je Gerät einstellbar). Die Einstellungen werden
berücksichtigt:</p>
<ul>
<li>weniger als 6½ Digits: zusätzlicher Rauschfehler;</li>
<li>2-Draht-Widerstand ohne Null: +0,2 Ω für die Messleitungen;</li>
<li>Autozero aus: kleiner Zusatzfehler;</li>
<li>Wechselspannung und -strom: der Fehler hängt von der <b>Signalfrequenz</b> (eintragen,
Standard 50 Hz) und vom AC-Filter ab; Signale unter 5 % des Bereichs bekommen einen
Zusatzfehler;</li>
<li>Frequenz und Periode: der Fehler hängt von der Gate-Zeit ab.</li>
</ul>
<p>Das Feld unter den Einstellungen zeigt h für den letzten Messwert (oder einen Beispielwert) samt
Begründung.</p>
<p><b>Welche Zeit seit Kalibrierung?</b> Das Datenblatt nennt jede Genauigkeit in drei Spalten.
Das Gerät driftet nach der Kalibrierung langsam weg, deshalb wächst der erlaubte Fehler mit der
Zeit:</p>
<table>
<tr><th>Einstellung</th><th>Bedeutung</th></tr>
<tr><td>24 Stunden (23 °C ± 1 °C)</td><td>direkt nach der Kalibrierung, im klimatisierten Labor –
nur für Sonderfälle</td></tr>
<tr><td>90 Tage (23 °C ± 5 °C)</td><td>innerhalb der letzten drei Monate kalibriert</td></tr>
<tr><td>1 Jahr (23 °C ± 5 °C)</td><td><b>Normalfall</b>: Gerät mit jährlicher Kalibrierung</td></tr>
</table>
<p>Beispiel 1-kΩ-Bereich, 1 Jahr: ± (0,010 % vom Messwert + 0,001 % vom Bereich); bei 108,6446 Ω
sind das 10,9 mΩ + 10 mΩ ≈ <b>21 mΩ</b>. Das Kalibrierdatum des Geräts kennt das Tool nicht – die
Spalte wählen, die zum Kalibrierintervall passt.</p>
<p><b>Grenzen:</b> Das Datenblatt gilt bei 18 … 28 °C nach einer Stunde Aufwärmzeit. Bei
Autorange wird der kleinste Bereich angenommen, in den der Wert passt (auf der sicheren Seite).
Für dB/dBm und das Spannungsverhältnis nennt das Datenblatt keinen einfachen Wert; u enthält dann
nur den zufälligen Anteil, ein Hinweis weist darauf hin.</p>

<h3>Wie viele Messwerte?</h3>
<p>Eine Standardabweichung braucht mindestens <b>4 Messwerte</b>. Bei weniger Werten wird das
Ergebnis als <i>nicht valide</i> markiert, und u enthält nur den Gerätefehler h (wie bei einer
Einzelmessung). Die Planungsanzeige warnt schon vor dem Start, wenn eine Messung weniger als
4 Messwerte liefert.</p>
<p>Mehr Messwerte verkleinern den zufälligen Anteil, aber nie h. Sobald t · s(x̄) klein gegenüber h
ist, verbessern weitere Messwerte das Ergebnis kaum noch – im Beispiel überwiegt h schon bei fünf
Messwerten. Messwerte mit Überlauf oder Fehler werden nicht verwendet und gesondert gezählt.</p>

<h3>Umrechnung</h3>
<ul>
<li><b>Linear</b>: y = Faktor · x + Offset mit eigener Einheit, z. B. ein 4–20-mA-Drucksensor für
0–10 bar: Faktor 625, Offset −2,5, Einheit bar.</li>
<li><b>Pro Länge</b>: Messwert ÷ Leitungslänge, z. B. Ω/m bei Kabelprüfungen.</li>
</ul>
<p>Das Ergebnis wird mit umgerechnet, u wird mit dem Faktor multipliziert:
(12,000 ± 0,019) mA → (5,000 ± 0,012) bar. Die Unsicherheit des Sensors oder der Leitungslänge kennt
das Tool nicht; sie ist nicht enthalten.</p>

<h3>Wo finde ich was?</h3>
<ul>
<li><b>Anzeigekachel</b>: x̄ ± u während der Messung, dazu s, h, min, max und n.</li>
<li>Reiter <b>Übersicht</b>: je Gerät und Objekt eine Zeile mit allen Zwischenwerten.</li>
<li><b>TXT-Protokoll</b>: die vollständige Rechnung je Gerät, einschließlich der Hinweise.</li>
</ul>

<h3>Ohne Messunsicherheit</h3>
<p>Wenn nur die Messwerte und ihre Statistik interessieren, <i>Messunsicherheit berechnen</i>
ausschalten. Dann werden nur Mittelwert x̄, Standardabweichung s, s(x̄), Minimum und Maximum
berechnet; t, h und u entfallen in Kachel, Übersicht und Export, und die Warnung vor zu wenigen
Messwerten verschwindet. Die Umrechnung funktioniert weiterhin.</p>"""),
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
weiß …), eines pro Zeile in der Reihenfolge der Messung – oder eine Vorlage wählen. Eigene Listen
lassen sich mit <i>Als Vorlage speichern …</i> aufheben: Vorlage wählen, Liste ändern und unter
demselben Namen speichern, um sie zu bearbeiten. <i>Vorlage löschen</i> entfernt sie; gelöschte
Standardvorlagen holt <i>Standardvorlagen wiederherstellen</i> zurück.</li>
<li>Messdauer je Objekt einstellen (oft <i>1 Messwert</i> oder wenige Sekunden).</li>
<li><i>Messung starten</i>: ein Banner zeigt, welches Objekt an welches Gerät anzuschließen ist.
Anschließen und <b>Messen</b> drücken (oder Enter).</li>
<li>Mit zwei Geräten hat jedes seine eigene Liste: unter <i>Liste bearbeiten für</i> wählen,
welche Liste angezeigt wird. In jedem Schritt misst jedes Gerät sein nächstes Objekt (z. B. T034 →
rot, T049 → weiß). Ein Gerät mit kürzerer Liste pausiert in den letzten Schritten, eines ohne
Objekte wird nicht gemessen.</li>
<li><i>Letzten Schritt wiederholen</i> misst das vorige Objekt erneut (z. B. nach einem
Wackelkontakt), <i>Überspringen</i> lässt ein Objekt aus, <i>Messreihe beenden</i> bricht vorzeitig
ab.</li>
<li>Alternativ <i>Automatisch nach Pause</i>: der nächste Schritt startet nach Ablauf der
Pause.</li>
</ol>
<p>Der Reiter <b>Übersicht</b> zeigt je Objekt eine Zeile mit n, x̄, s, s(x̄), t, h, u und dem
Ergebnis x̄ ± u. Das TXT-Protokoll beginnt mit derselben Tabelle.</p>
<h3>Messen bis stabil</h3>
<p>Statt einer festen Dauer misst jedes Gerät, bis sich die Werte beruhigt haben: Die Spannweite
(Max − Min) der letzten N Messwerte muss innerhalb einer Grenze liegen – in % vom Messwert oder
absolut. Die Messdauer gilt dann als Höchstdauer. Der Mittelwert der letzten N Messwerte ist der
<b>Endwert</b>. Typisch für Temperaturprüfungen, lange Leitungen und Sensoren mit
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
<li><b>MIN / MAX / Ø</b> laufen seit der letzten Änderung oder seit <i>Zurücksetzen</i>.
<i>Zurücksetzen</i> leert auch das Diagramm dieses Geräts (eine laufende Aufnahme behält alle
Messwerte).</li>
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
optional berechneter Wert, Status und Rohwert. Format: Deutsch (Semikolon,
Dezimalkomma – öffnet direkt in deutschem Excel) oder international.</li>
<li><b>TXT</b>: lesbares Protokoll mit allen Einstellungen, dem Messergebnis x̄ ± u samt allen
Zwischenwerten, Übersicht und allen Messwerten.</li>
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
<p>Außerdem: Selbsttest, Fehlerspeicher, Reset (*RST) und Signalton-Test.</p>"""),
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
