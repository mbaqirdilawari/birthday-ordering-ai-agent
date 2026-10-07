# Sample conversation (demo mode, simulated data)

**Customer:** Hi! I want an ice cream trike for my daughter's birthday

**Agent:** Hello! I can book an ice cream trike for your birthday party. How many children are coming, and on which date?

**Customer:** About 18 kids, on 17 October

> tool `recommend_bundle` called with `{'num_children': 18}`

**Agent:** For 18 children I suggest Classic Party Pack (10 x Chocolate Cone; 10 x Chocolate Bar; 20 x Vanilla Cup), PKR 3,600. Which time slot (12 to 3, 3 to 6, or 6 to 9) and which area of Karachi?

**Customer:** Evening please, we live in Gulshan-e-Iqbal

> tool `check_availability` called with `{'area': 'Gulshan-e-Iqbal', 'event_date': '2026-10-17', 'slot': '18:00-21:00', 'bundle_id': 'B2', 'bundle_quantity': 1}`

**Agent:** Good news: a trike is free on 2026-10-17, 18:00-21:00 in Gulshan-e-Iqbal. To book it, please share your name, a phone number and the full address.

**Customer:** My name is Sara Ahmed, phone 0300 1234567

**Agent:** To book it, please share the full address.

**Customer:** Address is House 12, Block 5, Gulshan-e-Iqbal. It is on the 2nd floor, theme is Unicorns

> tool `quote_order` called with `{'bundle_id': 'B2', 'bundle_quantity': 1}`

**Agent:** Please confirm: 1 x Classic Party Pack on 2026-10-17, 18:00-21:00, at House 12, Block 5, Gulshan-e-Iqbal (Gulshan-e-Iqbal, floor 2, theme: Unicorns) for Sara Ahmed, 03001234567. Total PKR 3,600, cash on delivery. Shall I book it?

**Customer:** yes

> tool `create_booking` called with `{'customer_name': 'Sara Ahmed', 'phone': '03001234567', 'area': 'Gulshan-e-Iqbal', 'address': 'House 12, Block 5, Gulshan-e-Iqbal', 'event_date': '2026-10-17', 'slot': '18:00-21:00', 'bundle_id': 'B2', 'bundle_quantity': 1, 'floor': 2, 'decoration_theme': 'Unicorns'}`

**Agent:** Booked! Your booking id is BK0001. The trike arrives on 2026-10-17 at the start of 18:00-21:00. Please pay PKR 3,600 in cash on the day. Our team will bring an insulated carry box for the upper floor.

**Customer:** Can you check BK0001?

> tool `get_booking` called with `{'booking_id': 'BK0001'}`

**Agent:** Booking BK0001 is Confirmed: 2026-10-17, 18:00-21:00, Gulshan-e-Iqbal. Total PKR 3,600, cash on delivery.

## Order routing after the booking

| Sent to | Message |
|---|---|
| Distributor | New birthday event BK0001: 1 x Classic Party Pack, 2026-10-17 18:00-21:00, Gulshan-e-Iqbal. Assign trike D03-T1 and load stock. |
| Cold chain team | Plan cold chain for BK0001: 1 x Classic Party Pack, 2026-10-17 18:00-21:00, Gulshan-e-Iqbal. Items: 10 x Chocolate Cone, 10 x Chocolate Bar, 20 x Vanilla Cup. |
| Territory manager | Event booked in your territory: BK0001: 1 x Classic Party Pack, 2026-10-17 18:00-21:00, Gulshan-e-Iqbal. |
| Event staffing supervisor | Staff event BK0001: 1 x Classic Party Pack, 2026-10-17 18:00-21:00, Gulshan-e-Iqbal. Address: House 12, Block 5, Gulshan-e-Iqbal, floor 2. Uniform check and trike decoration: Unicorns. Bring an insulated carry box (upper floor). |
| Head office project team | Booking logged BK0001: 1 x Classic Party Pack, 2026-10-17 18:00-21:00, Gulshan-e-Iqbal. Total PKR 3,600 cash on delivery. |
| Customer | Confirmed BK0001: 1 x Classic Party Pack, 2026-10-17 18:00-21:00, Gulshan-e-Iqbal. Pay PKR 3,600 in cash on the day. |
