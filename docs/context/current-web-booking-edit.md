# WEB booking edit status

Issue: #191
Branch: `feat/web-booking-edit`

Implemented:
- owner-scoped web endpoints for booking reschedule and cancel;
- same-origin boundary validation on both mutations;
- editable future scheduled booking cards in day/week calendar;
- reschedule dialog with Moscow date/time input;
- explicit cancel confirmation;
- calendar refresh after successful mutation;
- mobile layout;
- backend and static asset regression tests.

No automatic client messages are sent. Booking history remains stored.
