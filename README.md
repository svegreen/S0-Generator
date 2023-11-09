# S0-Generator
Mein Wechselrichter/Speicher von **SENEC** und meine Wärmepumpe von **iDM** bieten jeweils reichlich Schnittstellen, aber leider keine Gemeinsame. Deshalb lese ich mit diesem Skript die aktuellen PV-Leistungen im lokalen Netzwerk aus und generiere damit ein **S0-Signal** ([Wiki](https://de.wikipedia.org/wiki/S0-Schnittstelle)), das die Navigator Steuerung der iDM Wärmepumpe verarbeiten kann.

Damit kann die Wärmepumpe die Warmwasserbereitung abhängig vom Solar-Etrag heißer fahren als normal. So nutzt sie den günstigen Solarstrom um den Warmwasserspeicher auf eine höhere Temperatur zu bringen. Dessen Ladung hält dann länger und spart so womöglich eine spätere zusätzliche Warmwasserladung mit teurem Netzstrom (weil dunkel). Bei unserer Anlage macht sich das besonders in den Übergangsjahreszeiten bemerkbar, wenn schon deutlicher Heizbedarf besteht, aber trotzdem immer mal wieder noch kräftig Leistung vom Dach kommt.

## Installation
### PIGPIO
Zur Erzeugung des Pulses verwenden wir [PIGPIO](http://abyz.me.uk/rpi/pigpio/python.html), das muss installiert werden
```
sudo apt-get update
sudo apt-get install pigpio python-pigpio python3-pigpio
```
Allerdings muss auch der `pigpiod`-Dienst dazu laufen, weshalb wir den nach jedem Boot automatisch mit starten wollen:
```
sudo systemctl enable --now pigpiod
```
### senec.py
Weiterhin verwenden wir zur bequemen Abfrage des Wechselrichters [senec.py von smashnet](https://gist.github.com/smashnet/82ad0b9d7f0ba2e5098e6649ba08f88a). Die Datei muss einfach im gleichen Verzeichnis liegen.

### Erster Start
Im Skript muss man eigentlich nur die IP-Adresse vom eigenen SENEC-Wechselrichter anpassen und schon lässt es sich starten:
```
python S0-Generator.py
```
Die Ausgabe ist ganz interessant um das Skript besser zu verstehen. Jetzt sollten regelmäßig die relevanten Betriebsdaten geholt und angezeigt werden. Der IO-Pin sollte entsprechende Pulse generieren. Die Ausführung lässt sich mit Str+C beenden

### Dauerhaft einrichten
Wenn beim manuellen Start alles geklappt hat, sollte man das Skript ebenfalls als Dämon einrichten, der automatisch mitgestartet wird. Dazu habe ich diese [Anleitung](https://raspberrypi.stackexchange.com/questions/108694/how-to-start-a-python-script-at-boot) verwendet.
```
sudo systemctl --force --full edit S0-Generator.service
```
Ergänzt habe ich die Angabe des Users, unter dem das Skript laufen soll und das -u Flag, damit die print-Ausgaben auch sofort im Protokoll des Service angezeigt werden (unbuffered):
```
[Unit]
Description=Script to poll Senec PV-power and generate S0-pulses for iDM heat pump
After=multi-user.target

[Service]
User=pi
ExecStart=python3 -u /home/pi/S0-Generator.py

[Install]
WantedBy=multi-user.target
```
```
sudo systemctl enable --now S0-Generator.service
```
```
systemctl status S0-Generator.service
```

## Hardware
Die Pulse kommen aktuell auf PIN 17 raus. Dort habe ich einen Optokoppler angeschlossen,über den die Wärmepumpe galvanisch getrennt angebunden ist.
TODO: Schaltplan

## Funktion
In der iDM-Steuerung kann man für den S0-Eingang zwischen Erstrags- und Überschussregelung wählen. Letzteres funktioniert bei mir besser, weil dann wirklich nur die Leistung betrachtet wird, die von keinem anderen Verbraucher im Huas beansprucht wird. Logischerweise bricht dieser Wert dann allerdings deutlich ein, sobald die Wärmepumpe anspringt; das berücksichtigt die iDM aber wenn man diesen Modus verwendet (sonst müsste sie ja gleich wieder abschalten und es ginge hin&her).

Weiter habe ich festgestellt, dass eine leerer Akku langsamer geladen wird, also morgens erst mal wenig Leistung zieht, diese aber dann mit zunehmendem Füllstand steigert. Deshalb ist morgens oft recht viel Überschuss-Leistung vorhanden. Weil mir ein voller Akku erst mal wichtiger ist und der Warmwasserbedarf über den Tag eher gering ist, möchte ich, dass die Wärmepumpe erst später anläuft.

Das Skript fragt deshalb in regelmäßigen Intervallen die Solar-Leistung, die eingespeiste Leistung (Überschuss) und den Batterie-Füllstand ab. Abhängig vom Füllstand wird dann der Wärmepumpe eine geringere Leistung vorgegaukelt, so dass diese noch nicht anspringt. Erst wenn der Akku halbwegs voll ist, selber mit voller Leistung geladen wird und dann immer noch genug Leistung ins Netzt geht, darf die Wärmepumpe loslegen.
