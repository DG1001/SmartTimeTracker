# SmartTimeTracker

Eine einfache Webanwendung zur Zeiterfassung mit Benutzer- und Admin-Dashboard.

## Features

- Benutzer-Login per Token (auch Direktlogin per URL-Parameter `?token=...`)
- Zeiteinträge erfassen, bearbeiten und löschen
- Admin-Dashboard zur Benutzer- und Projektverwaltung
- CSV-Export aller Zeiteinträge im Admin-Dashboard
- Statusverwaltung für Zeiteinträge (OK / Nicht OK)
- Projektliste im Adminbereich mit Gesamtstunden als Apple-OS-ähnliche Tabelle

## Installation

1. Repository klonen:
   ```bash
   git clone <repository-url>
   cd <projektverzeichnis>
   ```

2. Abhängigkeiten installieren:
   ```bash
   pip install -r requirements.txt
   ```

3. Anwendung starten:
   ```bash
   python app.py
   ```

4. Im Browser öffnen:
   ```
   http://localhost:5000
   ```

## Nutzung

- Admin-Login über `/admin/login` mit festgelegtem Passwort (`admin123`).
- Benutzer-Login über `/user/login` mit Token oder Direktlogin per URL-Parameter.
- Im Admin-Dashboard Benutzer und Projekte anlegen, Projekte Benutzern zuweisen.
- Benutzer können ihre Zeiteinträge erfassen, bearbeiten und löschen.
- Admin kann alle Zeiteinträge einsehen, Status setzen und als CSV exportieren.

## Sicherheitshinweis

- Das Admin-Passwort ist aktuell fest im Code hinterlegt und sollte für den produktiven Einsatz geändert werden.
- Tokens für Benutzer sind zufällig generiert und dienen als Authentifizierung.

## Lizenz

Dieses Projekt ist unter der MIT-Lizenz lizenziert.
