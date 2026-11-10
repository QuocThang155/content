"""THANG MIA domain logic shared by the web API.
Pure business rules only: no Tkinter, external API, or full-story storage.
"""
from __future__ import annotations
import csv
import datetime as dt
from difflib import SequenceMatcher
import json
import math
import os
from pathlib import Path
import random
import re
import sys
import unicodedata
import uuid

APP_NAME = 'THẮNG MIA • Offline Studio'
VERSION = '2.0.0'
TOTAL = 42
AI_COUNT = 3
APP_HOME = Path.home() / '.story42_offline'
DATA_FILE = APP_HOME / 'project.json'

COL = {
    'bg': '#0B1220', 'panel': '#141F31', 'card': '#19283D', 'card_light': '#1D3049',
    'border': '#30435A', 'text': '#F0F5FA', 'muted': '#AAC0D2', 'accent': '#46C3B3',
    'blue': '#87BFFF', 'warning': '#FFD17A', 'danger': '#FF9A98', 'input': '#111C2D',
}
THEMES = [
    ('FAMILY', 'Gia đình & trách nhiệm'),
    ('ESTATE', 'Tài sản & quyền lợi'),
    ('OFFICE', 'Công sở & nghề nghiệp'),
    ('SHOP', 'Kinh doanh nhỏ'),
    ('SCHOOL', 'Trường học & giáo dục'),
    ('CARE', 'Chăm sóc & bệnh viện'),
    ('HOUSING', 'Nhà ở & khu dân cư'),
    ('TRANSIT', 'Di chuyển & giao thông'),
    ('RURAL', 'Nông thôn & sinh kế'),
    ('EVENTS', 'Sự kiện & lễ cưới'),
    ('FRIENDS', 'Bạn bè & lòng tin'),
    ('ONLINE', 'Danh tiếng cộng đồng'),
    ('SERVICE', 'Lao động dịch vụ'),
    ('ARTS', 'Văn hóa & thể thao'),
]
THEME_NAME = dict(THEMES)

# This is a starter bank of 126 differentiated plot briefs, NOT 126 full stories.
# Nine seed briefs per theme cover three sets of 42 without recycling a seed.
# To keep publishing new ideas sustainably, import newly planned briefs regularly.
# Fields: theme ~ title ~ hero ~ antagonist ~ unfair action ~ evidence ~ reversal ~ resolution
SEED_LINES = r'''
FAMILY~The Empty Chair~A daughter caring for her retired father~A favored older brother~He removes her from a family celebration and claims she has abandoned their father~The father's appointment calendar and neighbors' dated visit notes~The brother arranged the gathering on the only evening she was at a scheduled clinic visit~The family openly credits the caregiver and sets fair responsibilities
FAMILY~The Missing Lunchbox~A single father serving as a school volunteer~A status-conscious aunt~She tells relatives that he never packs meals for his child~A school lunch log and the child's handmade thank-you notes~The aunt has been taking credit for deliveries the father arranged~The school corrects the story and the father sets firm boundaries
FAMILY~The Quiet Grandmother~A granddaughter managing house repairs~An uncle seeking admiration~He accuses her of wasting the grandmother's savings on unnecessary work~Contractor invoices and before-and-after inspection notes~The disputed repairs were required to keep the grandmother's home accessible~The relatives share the real costs and apologize
FAMILY~The Unexpected Guest~An adopted son hosting a family reunion~A cousin who guards family traditions~The cousin removes his name from the reunion program and says he is not family~A decades-old reunion album and the organizer's notes~The late grandparents had named him the reunion's first volunteer host~The family restores his place and revises the tradition
FAMILY~The Sunday Grocery Bag~A mother working evening shifts~Her adult son seeking control of family spending~He publicly claims she gives all her attention to strangers instead of relatives~Receipts and a community pantry's service roster~The groceries were for an elderly neighbor the son had promised to assist~The son takes responsibility and the family agrees on a shared plan
FAMILY~The Birthday Envelope~An older sister paying household expenses~A younger sibling who wants praise~The sibling stages a surprise party and blames the sister for missing it~A shared work rota and a venue booking record~The party was deliberately booked during the sister's non-transferable shift~The family stops treating attendance as proof of love
ESTATE~The Workshop Key~A woman restoring a family workshop~A distant relative demanding the property~He changes the access rules and claims her investment was unauthorized~A signed maintenance agreement and the workshop's inventory history~The property's use rights were already assigned to the restorer~The access decision is reversed through proper mediation
ESTATE~The Garden Boundary~A retired teacher tending a community plot~A developer's local representative~He fences off the vegetable beds and calls them abandoned land~A municipal allotment map and dated planting records~The fence crosses a protected shared-use strip~The barrier is removed and the garden stewardship is renewed
ESTATE~The Forgotten Storage Room~A small museum caretaker~A board member seeking a private sale~She labels stored exhibits as ownerless junk and moves to dispose of them~An archived donation catalog and numbered exhibit tags~The collection has binding community ownership conditions~The sale is canceled and an open inventory policy begins
ESTATE~The Last Market Stall~A vendor who inherited a stall permit~A market association officer~He offers the stall to his friend and claims the permit has expired~Renewal receipts and the association's meeting minutes~The officer withheld the vendor's completed renewal from the agenda~The permit is restored after an independent review
ESTATE~The Family Boat~A fisherman's daughter maintaining a small boat~A cousin who wants to lease it out~He alleges the daughter never contributed to maintenance~A dated repair ledger and independent mechanic's records~The boat can legally be leased only with the named caretaker's approval~The family reaches a transparent use agreement
ESTATE~The Bookshop Lease~A widow managing a neighborhood bookshop~A property agent chasing a higher commission~The agent announces an early eviction without showing authority~The signed lease renewal and landlord's written confirmation~The landlord had extended the lease before the agent made the claim~The shop stays open and the agent loses the assignment
OFFICE~The Presentation Credit~A junior analyst who built a client proposal~A manager seeking promotion~The manager removes her name and presents the work as his own~Versioned draft history and meeting agenda notes~The client specifically requested the analyst's original design~Credit and responsibility are corrected by leadership
OFFICE~The Shift Swap~A night-shift nurse scheduling staff coverage~A supervisor favoring a friend~The supervisor blames the nurse for a staffing shortage~Approved roster changes and a shift handover notebook~The supervisor canceled confirmed coverage without informing the team~The hospital revises scheduling controls and clears the nurse
OFFICE~The Training Certificate~A warehouse trainer mentoring new workers~A team leader protecting a poor performer~He claims the trainer never provided required instruction~Signed attendance sheets and routine assessment results~The alleged untrained worker missed the sessions after the leader reassigned him~The worker receives training and the false report is withdrawn
OFFICE~The Broken Display~A retail visual merchandiser~A store manager who cut the display budget~She blames him for a failed promotional event~Purchase orders and the approved mock-up~The final display differed because the manager secretly removed required materials~Management corrects the review and fixes procurement approval
OFFICE~The Missing Byline~A local journalist preparing a neighborhood feature~An editor promoting a favorite writer~The editor publishes the feature under someone else's name~Editorial drafts and a recorded planning meeting summary~The source interviews were done by the original reporter~A correction and fair credit policy follow
OFFICE~The Factory Suggestion~An equipment technician proposing a safety improvement~A department chief concerned about reputation~He dismisses the technician's plan and claims she caused production delays~Pilot inspection results and dated maintenance notes~The chief postponed the safe trial after it was formally approved~The improvement is adopted and the blame is corrected
SHOP~The Bakery Order~A home baker supplying a fundraiser~A competing baker on the committee~The rival says the order arrived late and demands compensation~Pickup confirmation and the event organizer's checklist~The rival changed the pickup point without telling the baker~The organizer sets the record straight and pays fairly
SHOP~The Sari-Sari Shortfall~A sari-sari store assistant~An owner who ignores inventory controls~The owner accuses the assistant of missing stock~Opening counts, delivery records, and a supplier correction slip~The supplier had double-counted a shipment that never arrived~The assistant is cleared and stock checks are improved
SHOP~The Flower Cart Spot~A flower seller working at a transport hub~A new vendor backed by an organizer~The organizer orders her cart moved and claims she has no reservation~A printed event stall allocation and fee receipt~Her assigned location was handed to a late-paying vendor~The agreed spot is returned and allocation becomes public
SHOP~The Food Truck Queue~A food truck owner preparing for a fair~A fair coordinator favoring a sponsor~The coordinator falsely accuses the truck of jumping the registration queue~The dated registration list and inspection clearance~The sponsor was inserted after the official deadline~The truck gets its rightful spot and the fair adopts clear rules
SHOP~The Tailor's Deposit~A young tailor accepting a uniform contract~A purchasing officer trying to shift costs~The officer says the tailor lost a customer's deposit~A job order, a receipt stub, and a fabric delivery note~The officer approved a size change after production started~The company pays for the approved changes and repairs trust
SHOP~The Plant Nursery Labels~A nursery worker caring for special plants~A business partner chasing quick sales~The partner claims the worker mislabeled expensive seedlings~Batch labels and propagation logs~The partner switched the labels while rearranging the sales section~The store corrects customers' orders and the worker receives credit
SCHOOL~The Scholarship Board~A scholarship applicant volunteering at school~A committee member supporting a relative~The member removes her application as supposedly incomplete~The stamped checklist and submission acknowledgment~The applicant filed all requirements before the cutoff~A fair review restores her application
SCHOOL~The Science Exhibit~A student building a water-saving exhibit~A classmate eager for the trophy~The classmate claims the student copied the model~Design sketches and progressive build photographs~The accuser attended the student's earlier design workshop~Judges restore proper authorship and the classes learn collaboration rules
SCHOOL~The Parent Meeting~A guardian working rotating shifts~A parent representative seeking control~She says the guardian never participates in school activities~Volunteer records and approved remote meeting notes~The guardian contributed while assigned to evening shifts~The school offers accessible meeting options
SCHOOL~The Missing Library Books~A school librarian on contract~An administrator preparing budget cuts~He accuses her of losing a set of donated books~Catalog accession numbers and a storage transfer log~The books were moved by the administrator's renovation team~The librarian keeps her post and a checkout process is introduced
SCHOOL~The Graduation Program~A quiet student leading a community project~A club officer seeking recognition~The officer deletes the student's name from the graduation presentation~Project correspondence and the community partner's acknowledgment~The partner's original sponsorship named the student's leadership~The program is corrected before the ceremony
SCHOOL~The Classroom Mural~An art teacher organizing a student mural~A school supplier hoping for a private contract~The supplier says the mural damaged school property~Approval notes and before-and-after site photographs~The marked wall was allocated for an officially approved project~The mural remains and transparent project approval follows
CARE~The Volunteer Schedule~A home-care worker supporting a senior citizen~A relative who wants to reduce care costs~The relative says the worker routinely misses appointments~Signed care visits and a clinic calendar~The relative repeatedly rescheduled the visits without informing the household~The care contract is fairly reviewed and visits stabilized
CARE~The Hospital Meal Tray~A dietary aide at a hospital~A contractor who cut ingredient deliveries~The contractor blames the aide for incomplete meal trays~Approved menu sheets and kitchen receiving logs~The contractor had delivered fewer supplies than contracted~The hospital replaces the missing meals and corrects accountability
CARE~The Pharmacy Waiting Line~A pharmacy clerk assisting senior patients~A supervisor favoring a VIP customer~She says the clerk ignored an older customer on purpose~Queue tickets and the duty assignment chart~The supervisor diverted staff at the exact time of the delay~The clerk is cleared and a fair queue policy is posted
CARE~The Community Clinic Van~A driver transporting clinic supplies~A program coordinator under deadline pressure~The coordinator says the driver skipped a scheduled barangay stop~Route manifests and a signed delivery acknowledgment~The stop had been removed by the coordinator after public notices went out~The program announces a corrected schedule and accountability
CARE~The Donation Shelf~A clinic volunteer arranging donated supplies~A committee officer wanting publicity~The officer accuses the volunteer of hiding donation boxes~Stock intake lists and the charity's collection summary~The boxes were placed in a reserved distribution area the officer approved~The officer apologizes and the clinic adopts clear labeling
CARE~The Therapy Garden~A groundskeeper maintaining a wellness courtyard~An administrator prioritizing a showcase event~The administrator blames him for an untidy garden before a visit~Work orders and event setup photographs~The display crew blocked access despite a scheduled maintenance slot~The staff coordinate future events and the groundskeeper is vindicated
HOUSING~The Shared Corridor~A renter organizing cleaning days~A homeowners' officer running for reelection~The officer fines her for litter in a shared hallway~Building cleaning logs and corridor camera timestamps provided by management~The waste was left by an approved contractor after the cleanup~The fine is canceled and contractor rules are enforced
HOUSING~The Water Meter Mix-Up~A tenant caring for 2 younger siblings~A landlord rushing to collect extra fees~The landlord accuses the tenant of abnormal water use~Maintenance readings and a plumber's repair summary~The leak came from a common pipe serving multiple units~Charges are recalculated and repairs completed
HOUSING~The Noisy Renovation~A homeowner who works nights~A neighboring renovation project lead~He claims she filed malicious complaints to stop his project~Permitted work hours and security's incident notes~The contractor repeatedly worked outside agreed hours~A reasonable schedule is enforced for both households
HOUSING~The Apartment Garden~A resident growing vegetables in planters~A building committee chair~She orders the garden removed and claims it blocks emergency access~Floor layout plans and a safety inspection note~The planters occupy a previously approved community corner~The committee allows safe planters under written guidelines
HOUSING~The Rooftop Laundry~A single mother renting a small room~A caretaker favoring a long-term tenant~The caretaker bans her from the common drying area~House rules and a posted weekly schedule~No exclusive right had been granted to the favored tenant~Access is shared and rules apply equally
HOUSING~The Lobby Parcel~A delivery recipient with limited mobility~A security shift leader who dislikes requests~He accuses her of collecting another resident's parcel~Package release log and building desk records~Two parcels were mislabeled during the shift handover~The package is returned and handovers are improved
TRANSIT~The Missed Ferry~A market worker commuting by ferry~A ticket officer seeking to cover a scheduling error~The officer claims the worker boarded too late and forfeited the ticket~Ticket issue time and the publicly posted sailing update~The announced departure time changed after tickets were sold~Valid tickets are honored and a notice policy is introduced
TRANSIT~The Bus Terminal Bench~A senior volunteer helping passengers~A terminal manager embarrassed by a complaint~The manager says the volunteer blocked an accessible waiting area~Terminal layout plan and maintenance crew sign-off~The manager had moved the bench for an event without posting a notice~Accessible seats are restored and the volunteer is thanked
TRANSIT~The Missing Delivery Crate~A bicycle courier carrying bakery orders~A dispatcher covering a mix-up~The dispatcher says the courier left a crate at the wrong shop~Signed loading records and the receiving shop's tally~The dispatcher put the crate on a different route at dispatch~The courier is cleared and the routing process changes
TRANSIT~The School Shuttle Stop~A school shuttle assistant helping children board~A coordinator trying to shorten routes~The coordinator alleges the assistant skipped a child~Approved stop list and guardians' arrival confirmations~The coordinator removed the stop without telling parents~The safe route is restored and notices go out
TRANSIT~The Last Train Ticket~A commuter assisting an older traveler~A station supervisor avoiding a refund~The supervisor claims the commuter used an invalid ticket~Receipt and official service interruption notice~The train was canceled after ticket validation~The traveler receives the correct fare adjustment
TRANSIT~The Market Loading Bay~A vendor moving fresh produce early morning~A commercial property attendant~The attendant charges her an unexpected priority fee~Posted loading rules and earlier allocation confirmations~The space was improperly sold twice by the attendant~Fees are returned and fair allocation resumes
RURAL~The Irrigation Turn~A young farmer organizing a water schedule~An influential field owner~He blocks her irrigation slot and claims she never registered~Water users' timetable and a signed field inspection note~The disputed slot was reassigned without a committee vote~The fair schedule is restored for small farms
RURAL~The Seed Cooperative~A cooperative bookkeeper protecting members~A purchasing chair with a preferred vendor~The chair blames her for late seed deliveries~Purchase approvals and supplier dispatch records~The chair delayed the purchase to favor a more expensive offer~Members correct the contract and establish oversight
RURAL~The Fisherfolk Ice Box~A dock worker coordinating cold storage~A wholesale buyer trying to pay less~The buyer says the worker spoiled a delivery~Temperature check log and handover records~The buyer delayed pickup past the agreed window~The worker receives full payment and clear pickup terms
RURAL~The Coconut Harvest Share~A tenant farmer maintaining a grove~A land agent changing harvest terms~The agent denies the farmer's agreed percentage after the harvest~Signed crop-sharing summary and season tally~The agent tried applying a new rate retroactively~The original terms are honored and documented going forward
RURAL~The Village Footbridge~A carpenter volunteering on a footbridge repair~A contractor unhappy with volunteer oversight~The contractor says the carpenter caused a deadline delay~Materials checklist and inspection notes~The purchased boards did not meet the agreed specification~Correct materials are supplied and the bridge is safely completed
RURAL~The Weekend Market Weights~A vegetable seller bringing produce from a small farm~A market inspector who favors a wholesaler~The inspector claims her measuring scale is unreliable~Calibration record and witnessed retest~The inspector had tested the scale on an uneven table~The penalty is withdrawn and proper testing is required
EVENTS~The Wedding Seating Chart~A wedding coordinator managing two families~A relative determined to exclude a guest~The relative publicly accuses the coordinator of deliberately omitting names~Approved seating chart versions and RSVP confirmations~The relative sent conflicting edits after the final approval~The families agree on a corrected guest list and the coordinator is paid
EVENTS~The Charity Concert Slot~A volunteer singer preparing for a fundraiser~A sponsor representative favoring another act~He removes her performance slot and calls her unreliable~Rehearsal attendance and the confirmed running order~The sponsor changed the program after tickets advertised her act~The organizer reinstates fair billing and explains the change
EVENTS~The Town Fiesta Booth~A community baker reserving a fiesta booth~A festival organizer promoting friends~The organizer claims the baker failed to pay the booth fee~A dated receipt and booth allocation list~The organizer had reassigned a paid stall to a late applicant~The baker receives the promised booth and an apology
EVENTS~The Reunion Photo Wall~A class volunteer assembling reunion photos~An alumni officer who dislikes former classmates~The officer says the volunteer excluded an entire graduating group~Photo submission emails and print-order proofs~The officer never forwarded that group's approved images~The missing pictures are added before opening night
EVENTS~The Children's Stage Props~A school parent making stage props~A producer avoiding additional payment~The producer accuses her of delivering the wrong designs~Approved sketches and change-request messages~The producer ordered revised props but refused to update the budget~The parent receives the agreed additional fee
EVENTS~The Memorial Scholarship Night~A community organizer coordinating a tribute~A committee member chasing attention~The member claims the organizer concealed a promised award~Program drafts and donor confirmation notes~The award was postponed by the donor before the event~The ceremony announces the accurate plan without public blame
FRIENDS~The Group Trip Deposit~A café worker managing a group holiday plan~A friend who canceled without warning~The friend tells the group the worker lost the shared reservation~Booking terms and cancellation acknowledgment~The friend had canceled the shared booking after the deadline~The group fairly divides the cost and rebuilds trust
FRIENDS~The Borrowed Recipe~A food blogger helping a childhood friend~A friend trying to claim a family recipe~The friend says the blogger stole the dish idea~Dated cooking journals and a community recipe contest entry~The blogger had shared her method as a free favor~Credit is restored and the friends choose respectful distance
FRIENDS~The Pet Adoption Drive~A volunteer matching rescue pets to homes~A fellow organizer seeking donations~The organizer claims the volunteer blocked genuine adopters~Screening checklists and adoption committee decisions~The rejected applicants were awaiting routine welfare checks~The drive publishes consistent criteria and the volunteer is cleared
FRIENDS~The Neighborhood Language Club~A tutor running free weekend lessons~A club treasurer wanting control~The treasurer tells families the tutor charges hidden fees~Lesson notices and parental attendance signatures~The fees came from an unrelated private program the treasurer advertised~The club separates the programs and apologizes
FRIENDS~The Forgotten Reunion Fund~A graphic designer planning a reunion~An old friend handling shared contributions~The friend claims the designer overspent the budget~Approved expense spreadsheet and event vendor receipts~The friend had omitted a refund from the shared totals~The numbers are corrected and the group agrees on transparency
FRIENDS~The Community Pantry Shift~A student distributing food parcels~A volunteer captain who favors a relative~The captain accuses the student of taking more parcels than allowed~Distribution tally and signed shift handover~The captain had entered one family twice in the daily list~The record is corrected and the captain steps down
ONLINE~The Market Review~A new café owner addressing a viral complaint~A former event contractor seeking a refund~The contractor posts that the café canceled a charity booking~A publicly shared event calendar and mutual cancellation acknowledgment~The contractor canceled the slot before the café booked another event~A calm public clarification resolves the dispute without harassment
ONLINE~The Recipe Video Credit~A cooking student posting short videos~A popular creator using the student's footage~The creator claims the student copied her clip~Original recording timeline and public upload dates~The student's full tutorial was published before the shortened version~The platform credits the original creator and the student moves forward
ONLINE~The Community Announcement~A barangay volunteer preparing event notices~A rival volunteer who wants the lead role~The rival claims the event date was deliberately concealed~Printed announcements and the public event board history~The rival removed an outdated announcement after approving the corrected date~The team issues a clear notice and shares responsibility
ONLINE~The Handmade Bag Photo~A craft seller photographing her designs~An influencer seeking a free product~The influencer publicly calls the seller dishonest about delivery times~Order confirmation and agreed production schedule~The influencer requested custom changes after the original deadline~The seller clarifies the timeline and honors fair orders
ONLINE~The Library Fundraiser Post~A student volunteer organizing a book drive~A school club leader wanting publicity~The leader says donated books never reached the library~Librarian's public intake summary and delivery-day photographs~The books were temporarily sorted at an approved storage room~The club posts a correction and credits all volunteers
ONLINE~The Festival Poster Error~A freelance designer creating a public poster~A committee chair avoiding embarrassment~The chair blames the designer for the wrong event time~Approved proof and posted event schedule~The chair approved an outdated time after the venue changed~The committee publishes corrected information and pays the designer
SERVICE~The Hotel Lost-and-Found~A hotel room attendant~A supervisor protecting a VIP guest~The supervisor accuses the attendant of failing to log a forgotten item~Lost-and-found receipt and shift transfer record~The item was moved to the front desk after the shift had ended~The attendant is cleared and tracking improves
SERVICE~The Restaurant Reservation~A front-desk host at a family restaurant~A manager favoring a regular customer~The manager blames the host for turning away a reservation~The reservation book and table release record~The manager had reassigned the booked table without telling the host~The guest receives a proper apology and the host's record is corrected
SERVICE~The Tailor's Apprentice~A trainee learning clothing alterations~A senior worker fearing competition~She deliberately swaps job tickets and claims the trainee ruined an order~Fitting notes and signed job-ticket sequence~The swapped ticket belongs to the senior worker's own job~The trainee receives fair training and an accurate review
SERVICE~The Cleaning Team Award~A sanitation worker coordinating a school cleanup~A contractor seeking an award for his company~The contractor falsely claims his private team did the work~Volunteer roster and before-and-after cleanup records~The school staff and volunteers did the job before the contractor arrived~The award is corrected and workers receive recognition
SERVICE~The Salon Training Day~A junior salon stylist covering a workshop~A lead stylist demanding exclusive tips~The lead stylist tells clients the junior canceled appointments~Appointment schedule and workshop attendance notes~The lead stylist moved clients without their approval~Bookings are restored and service rules are clarified
SERVICE~The Repair Shop Guarantee~A repair shop assistant helping customers~A shop owner attempting to avoid warranties~The owner blames the assistant for promising an impossible repair~Approved service terms and intake checklist~The owner had accepted the job after reviewing its limitations~The customer gets an honest remedy and the assistant is cleared
ARTS~The Dance Rehearsal Video~A community dancer leading rehearsals~A team captain seeking full credit~The captain says the dancer skipped key rehearsals~Rehearsal schedule and dated practice footage~The captain changed rehearsal times without notifying the team~The dancers adopt a shared schedule and recognize the lead's work
ARTS~The Local Football Kit~A youth coach raising funds for equipment~A club officer who wants control of donations~The officer alleges the coach bought the wrong uniforms~Team-approved sizes and delivery inspection notes~The officer placed an unauthorized last-minute color change~The club corrects the order and publishes clear approvals
ARTS~The Public Art Contest~A street muralist entering a public competition~A judging committee member promoting a friend~The member rejects her work as submitted late~Timestamped submission acknowledgment and contest entry log~Her entry arrived on time but was misplaced during sorting~The committee restores a fair review and updates the process
ARTS~The Community Choir Solo~A singer returning after a family emergency~A choir coordinator with a favorite performer~The coordinator claims the singer missed all auditions~Audition sign-in sheet and practice director's notes~The singer was approved for an alternate audition slot~The choir holds a transparent final selection
ARTS~The Basketball Court Booking~A school sports volunteer coordinating a youth tournament~A private league organizer seeking exclusive court use~The organizer tells families the youth event has no permission~Public court allocation schedule and filed event plan~The private league reserved a different date and mixed up the calendar~Both groups receive their correct slots and share future schedules
ARTS~The Heritage Museum Tour~A young local guide training new volunteers~A board representative marketing a premium tour~The representative accuses the guide of giving inaccurate history~Curator-approved tour script and archived exhibit captions~The representative promoted a commercial script the museum had rejected~The museum restores the accurate tour and recognizes the guide
FAMILY~The Care Calendar~A son coordinating visits for his mother after surgery~A sibling who wants sole credit for caregiving~The sibling tells relatives that he stopped helping once she returned home~A shared visit calendar and pharmacy pickup receipts~The son covered the night shifts that were missing from the family chat~The siblings publish a fair rota and thank each other for their work
FAMILY~The Recipe Notebook~A granddaughter preserving her family's recipes~An aunt who wants to sell a cookbook under her name~The aunt claims the granddaughter copied recipes without permission~Handwritten recipe cards with dates and family annotations~The grandmother had asked the granddaughter to organize the collection~The family agrees on shared credit and keeps the originals together
FAMILY~The School Pickup Promise~A father arranging pickups for two households~A relative who repeatedly changes the agreed schedule~The relative blames him for a child missing an after-school activity~The signed pickup plan and timestamped school office log~The relative changed the pickup person but never updated the school~The adults correct the record and use one shared schedule
ESTATE~The Riverside Footpath~A neighborhood volunteer documenting a public walkway~A nearby landlord seeking private access~The landlord blocks the path and says residents have no right to pass~A council map and years of maintenance requests~The path is listed as a maintained public easement~The council restores access and posts clear boundary markers
ESTATE~The Storage Unit Inventory~A tenant sorting a late relative's stored belongings~A facility manager seeking an unpaid-lien sale~The manager says the unit was empty before the tenant arrived~A signed inventory, dated entry receipt, and payment record~The facility attached another tenant's inspection form by mistake~The contents are secured and the records process is corrected
ESTATE~The Shared Orchard~A caretaker maintaining trees on a cooperative plot~A committee officer allocating harvest rights to friends~The officer says the caretaker abandoned the orchard~Seasonal work logs and cooperative meeting minutes~The caretaker's agreed maintenance role includes the disputed trees~The cooperative restores the allocation and publishes its rules
OFFICE~The Accessible Meeting Room~An office coordinator arranging an accessible client meeting~A director trying to hide a venue change~The director says the coordinator failed to reserve the room~The booking confirmation and facilities change notice~Facilities moved the meeting after the coordinator's approved reservation~The team acknowledges the change and adopts a documented booking handoff
OFFICE~The Translation Review~A bilingual clerk checking public service forms~A contractor rushing an unapproved version~The contractor blames the clerk for confusing instructions~Tracked revisions and the signed review checklist~The published form skipped the clerk's final corrections~The agency withdraws the faulty form and credits the reviewer
OFFICE~The Inventory Count~A stock assistant reconciling donated equipment~A supervisor trying to conceal a duplicate order~The supervisor accuses the assistant of losing several devices~Receiving records and two matching purchase invoices~The same delivery was entered twice under different project codes~The count is corrected and the duplicate-order control is improved
SHOP~The Weekend Bread Stall~A baker preparing a stall for a neighborhood market~A market captain reserving prime space for a friend~The captain says the baker missed the application window~A timestamped application receipt and stall map~The captain changed the deadline after accepting the application~The baker receives an equivalent stall and future deadlines are posted publicly
SHOP~The Bicycle Repair Ticket~A mechanic repairing a commuter's bicycle~A shop owner trying to avoid a parts warranty~The owner says the mechanic installed the wrong component~The customer approval message and supplier warranty label~The owner substituted a cheaper part after the mechanic completed the work~The shop replaces the part and updates its approval process
SHOP~The Community Grocery Box~A small grocer assembling prepaid food boxes~A delivery partner keeping several boxes~The partner claims the grocer packed fewer items than promised~Packing checklist and signed delivery count~The missing boxes remained in the partner's van after a route change~The families receive their orders and the partners reconcile deliveries
SCHOOL~The Science Fair Table~A student team arranging an inclusive science display~A club officer reserving the best table for friends~The officer claims the team failed to submit its project~Submission receipt and teacher's project review notes~The officer filed the team's entry under the wrong category~The team presents its work and the fair adopts a numbered intake system
SCHOOL~The Library Reading Badge~A student librarian helping younger readers~A classmate claiming the student gave badges unfairly~Reading logs and the teacher-approved badge criteria~The classmate counted group reading sessions that were not eligible~The librarian followed the written rules consistently~The teacher clarifies the criteria and recognizes the volunteer
SCHOOL~The Bus Route Notice~A parent volunteer checking a school bus change~A transport coordinator avoiding a late update~The coordinator says the volunteer spread a false pickup time~The approved route bulletin and message delivery timestamps~The coordinator sent the corrected notice to an outdated group list~The school issues one verified channel for future route updates
CARE~The Therapy Room Booking~A clinic receptionist scheduling private therapy sessions~A manager favoring a high-profile client~The manager says the receptionist double-booked the room~The appointment ledger and electronic booking audit~The manager overrode the reservation without recording the change~The clinic restores the appointment and adds an approval trail
CARE~The Home Visit Record~A community nurse documenting a home wellness visit~A contractor disputing a missed service~The contractor claims the nurse never arrived~A signed visit form and the client's door log~The contractor used an outdated address supplied by dispatch~The service is rescheduled and dispatch verifies addresses
CARE~The Mobility Aid Return~A hospital aide tracking loaned mobility equipment~A department clerk trying to avoid a delayed return fee~The clerk blames the aide for keeping a wheelchair too long~The equipment checkout tag and ward transfer sheet~The wheelchair was moved with a patient before the return window began~The fee is canceled and equipment transfers are logged
HOUSING~The Laundry Room Schedule~A tenant representative posting fair laundry times~A resident claiming exclusive access~The resident says the representative removed their approved booking~The posted rota and building access timestamps~The resident had written a different unit number on the request~The manager confirms the schedule and introduces a shared booking board
HOUSING~The Roof Repair Notice~A building caretaker coordinating a roof inspection~A committee member who delayed approval~The member blames the caretaker for water damage~Inspection requests and a dated approval email~The repair team was kept from entering until the committee approved access~The building documents approvals and schedules the repair
HOUSING~The Community Room Deposit~A tenant group reserving a shared meeting space~A building agent withholding the deposit~The agent says the group left the room damaged~Pre-event photos and the signed room handover checklist~The damage was recorded in the room before the group's reservation~The deposit is returned and inspections become jointly documented
TRANSIT~The Ferry Queue Number~A commuter volunteer helping organize an accessible boarding line~A ticket clerk favoring a tour group~The clerk says the volunteer skipped the official queue~Numbered tickets and the boarding announcement log~The tour group was assigned a separate pre-booked boarding window~The operator restores the correct order and displays queue rules
TRANSIT~The Shared Ride Receipt~A driver delivering parcels on a rural route~A dispatcher disputing a fuel reimbursement~The dispatcher says the driver took an unauthorized detour~Route logs and a road closure bulletin~The detour was the only open road after a bridge inspection~The reimbursement is approved and route alerts are shared promptly
TRANSIT~The Station Lost Umbrella~A station attendant returning lost property~A senior clerk claiming the attendant misplaced it~The clerk says no umbrella was ever logged~A tagged property slip and platform camera time index~The item was moved to a different counter during a shift change~The owner retrieves it and handover records are standardized
RURAL~The Irrigation Turn~A farmer coordinating shared water access~A neighbor diverting water before the agreed time~The neighbor claims the farmer wasted the community supply~A dated gate log and the cooperative's rotation board~The neighbor opened the upstream gate during the farmer's turn~The cooperative restores the schedule and installs a shared reading gauge
RURAL~The Seed Donation Box~A village school aide distributing donated seed packets~A local organizer reserving the best packets for relatives~The organizer says the aide gave supplies to the wrong families~Signed distribution lists and donor packing notes~The packets were sorted by planting season, not household size~The village publishes simple criteria and completes a fair distribution
RURAL~The Mobile Clinic Stop~A community driver arranging a clinic visit to a remote hamlet~A coordinator canceling the stop without notice~The coordinator blames the driver for residents missing appointments~The route approval and clinic dispatch messages~The clinic changed its departure point after the driver had left~The team reschedules the visit and confirms changes with residents
EVENTS~The Festival Volunteer Pass~A volunteer coordinator assigning entry passes~A sponsor liaison reserving passes for guests~The liaison says the coordinator withheld passes from the cleanup crew~The signed volunteer roster and pass allocation sheet~The sponsor's late additions were mistakenly charged against volunteer passes~The crew receives access and future pass quotas are separated
EVENTS~The Community Hall Rehearsal~A youth group preparing a cultural performance~A hall custodian giving their rehearsal slot to another group~The custodian claims the youth group canceled~The reservation book and the group's arrival photo timestamp~The other group was given a duplicate booking by the office~Both groups receive fair rehearsal time and a single booking calendar is adopted
EVENTS~The Fundraising Auction List~A volunteer recording donated auction items~A committee treasurer hiding a missing listing~The treasurer blames the volunteer for omitting a valuable donation~The donor's receipt and the event intake log~The item was moved to a separate display before the catalog was printed~The item is added transparently and the donor is updated
FRIENDS~The Shared Studio Key~A ceramic artist sharing a weekend studio~A friend changing access without agreement~The friend tells the group the artist stopped paying rent~Transfer receipts and the studio's signed access schedule~The friend applied the payment to a different month without asking~The account is corrected and the artists agree on written terms
FRIENDS~The Volunteer Photo Album~A volunteer collecting photos after a charity event~A teammate claiming the album excluded their work~The teammate says the volunteer removed their contributions~Upload timestamps and the original shared folder history~The teammate's photos were stored in a private folder never submitted~The album is updated and the team agrees on one shared upload location
FRIENDS~The Group Gift Receipt~A friend organizing a retirement gift~A participant who kept part of the collected money~The participant accuses the organizer of spending too much~The group budget message and itemized store receipt~The extra amount was a refund the participant had not passed back~The friends settle the balance and use a shared ledger next time
ONLINE~The Neighborhood Noticeboard~A resident posting verified road closure updates~A page moderator seeking to embarrass a rival~The moderator labels the update fabricated and removes it~The city notice and the original post timestamp~The moderator had mistaken a second-phase closure for a cancellation~The page restores the post and adopts a correction policy
ONLINE~The Craft Tutorial Caption~A hobbyist sharing an accessible craft guide~A seller reposting the guide as paid instruction~The seller accuses the hobbyist of copying their product~Original drafts and the public tutorial date~The seller's product listing appeared after the free guide was published~The platform adds attribution and both clarify what each created
ONLINE~The Community Event Livestream~A student volunteering to stream a local event~A committee lead blaming the student for a missing recording~The lead says the student deleted the broadcast~Stream dashboard logs and the venue network outage report~The recording stopped when the venue connection failed~The committee shares the outage details and provides a written recap
SERVICE~The Parcel Counter Log~A counter clerk tracking customer parcels~A supervisor diverting a package to a private shelf~The supervisor accuses the clerk of releasing it without a signature~Dispatch scan and the customer collection receipt~The supervisor used a temporary shelf outside the clerk's assigned area~The parcel is traced and shelf custody is logged
SERVICE~The Catering Setup Checklist~A catering assistant arranging a community meal~A contractor cutting staff hours~The contractor claims the assistant missed the setup deadline~Signed arrival sheet and the venue's access record~The venue opened late after the contractor failed to collect the key~The assistant is paid for the extra time and access handovers are clarified
SERVICE~The Repair Appointment Window~A home-service scheduler assigning repair visits~A technician who wants a preferred route~The technician says the scheduler gave the customer the wrong time~Confirmed booking text and route assignment history~The technician accepted a later route but kept the old appointment note~The customer receives a new visit and dispatch records acknowledgments
ARTS~The Costume Rack List~A theater volunteer organizing borrowed costumes~A production lead reserving pieces for a private event~The lead says the volunteer lost several donated outfits~Signed loan cards and the rehearsal return checklist~The outfits were moved to a locked room by the production lead~The costumes are returned and future loans require two signatures
ARTS~The Youth Art Display~A student curator arranging a community art exhibit~A sponsor liaison removing unsigned pieces~The liaison claims the student ignored the exhibit rules~The approved submission list and the gallery intake labels~The sponsor changed the display criteria after selections were finalized~The original works are restored and selection rules are published
ARTS~The Music Room Schedule~A school music tutor coordinating practice time~A club officer reserving the room for friends~The officer says the tutor repeatedly missed bookings~The room key log and the tutor's lesson register~The officer moved practice sessions without updating the shared calendar~The school restores the lessons and starts a visible booking rota
'''.strip()

KEYS = ('theme', 'title', 'hero', 'antagonist', 'conflict', 'evidence', 'reversal', 'ending')
FIELDS = [('title', 'Tiêu đề'), ('hero', 'Nhân vật chính'),
          ('antagonist', 'Phản diện'), ('conflict', 'Hành động bất công'),
          ('evidence', 'Bằng chứng'), ('reversal', 'Cú đảo chiều'),
          ('ending', 'Kết thúc')]
STATUS_LABEL = {'ready': 'Chưa giao', 'sent': 'Đã giao', 'part1': 'Đã có Part 1', 'done': 'Hoàn tất'}
STATUS_COL = {'ready': COL['muted'], 'sent': COL['blue'], 'part1': COL['warning'], 'done': COL['accent']}
STOPWORDS = set('''a an the and or but for from this that these those of with in on at to by as is was were are be being been
his her their its who whom they them he she we our you your has have had not after before into during another one two three
someone now then while since about through over under only already any no must can should every when where which
người đã của và với trong là một để không cũng khi này kia được bởi nhưng cho còn người anh chị cô ông bà các những
claim claimed says say said says after work working family original proof shows reveal resolution final return story drama'''.split())
DUPLICATE_SYNONYMS = {
    'manager': {'manager', 'supervisor', 'boss', 'director', 'administrator'},
    'worker': {'clerk', 'assistant', 'employee', 'worker', 'staff'},
    'record': {'record', 'document', 'file', 'ledger', 'sheet', 'paper', 'paperwork', 'log', 'register'},
    'conceal': {'hide', 'hid', 'hidden', 'conceal', 'withhold', 'suppress'},
    'accuse': {'blame', 'blam', 'accuse', 'accus', 'allege'},
    'pay': {'pay', 'payroll', 'wage', 'salary', 'compensation', 'earning'},
    'improper': {'improper', 'unauthorized', 'unapproved', 'illegal', 'unlawful', 'wrongful'},
    'audit': {'audit', 'review', 'investigation', 'inspection', 'inquiry'},
    'relocate': {'move', 'relocate', 'transfer'},
    'lose': {'lose', 'lost', 'missing', 'absent'},
    'deduct': {'deduction', 'deduct'},
}
DUPLICATE_CANONICAL = {
    word: canonical
    for canonical, words in DUPLICATE_SYNONYMS.items()
    for word in words
}
BANNED_TOKENS = (
    'dugo', 'saksakin', 'tusukin', 'hiwain', 'magpaputok ng baril', 'barilin',
    'gahasain', 'butasin', 'tagusin', 'tagusan', 'lubusang tagusin',
    'direktang saksakin sa puso', 'direktang atake sa puso',
    'umaagos ang dugo na parang ilog', 'lawa ng dugo',
    'hiwain ang lalamunan', 'sakalin hanggang mamatay', 'tapusin',
    'basagin', 'baliin',
)


def seed_bank():
    bank = []
    for line_no, line in enumerate(SEED_LINES.splitlines(), 1):
        parts = [p.strip() for p in line.split('~')]
        if len(parts) != 8:
            raise ValueError(f'Bad seed line {line_no}: expected 8 fields, got {len(parts)}')
        obj = dict(zip(KEYS, parts))
        obj['id'] = f'SEED-{line_no:03d}'
        obj['source'] = 'starter'
        bank.append(obj)
    return bank


def today():
    return dt.date.today().isoformat()


def _token_sequence(text):
    normalized = unicodedata.normalize('NFKC', str(text)).lower()
    words = re.findall(r'[^\W_]+', normalized, flags=re.UNICODE)
    tokens = []
    for word in words:
        if word.endswith('ies') and len(word) > 5:
            word = word[:-3] + 'y'
        elif word.endswith('ing') and len(word) > 6:
            word = word[:-3]
            if len(word) > 2 and word[-1] == word[-2]:
                word = word[:-1]
        elif word.endswith('ed') and len(word) > 5:
            word = word[:-2]
        elif word.endswith('s') and len(word) > 4 and not word.endswith(('ss', 'us', 'is')):
            word = word[:-1]
        word = DUPLICATE_CANONICAL.get(word, word)
        if len(word) > 2 and word not in STOPWORDS:
            tokens.append(word)
    return tokens


def _text_similarity(a, b):
    tokens_a = _token_sequence(a)
    tokens_b = _token_sequence(b)
    if not tokens_a or not tokens_b:
        return 0.0

    set_a, set_b = set(tokens_a), set(tokens_b)
    overlap = set_a & set_b
    token_jaccard = len(overlap) / len(set_a | set_b)
    containment = len(overlap) / min(len(set_a), len(set_b))

    bigrams_a = set(zip(tokens_a, tokens_a[1:]))
    bigrams_b = set(zip(tokens_b, tokens_b[1:]))
    bigram_dice = (
        2 * len(bigrams_a & bigrams_b) / (len(bigrams_a) + len(bigrams_b))
        if bigrams_a and bigrams_b else 0.0
    )

    normalized_a = ' '.join(tokens_a)
    normalized_b = ' '.join(tokens_b)
    chargrams_a = {
        normalized_a[index:index + 3]
        for index in range(max(0, len(normalized_a) - 2))
    }
    chargrams_b = {
        normalized_b[index:index + 3]
        for index in range(max(0, len(normalized_b) - 2))
    }
    chargram_dice = (
        2 * len(chargrams_a & chargrams_b) / (len(chargrams_a) + len(chargrams_b))
        if chargrams_a and chargrams_b else 0.0
    )
    sequence_ratio = SequenceMatcher(
        None, normalized_a, normalized_b, autojunk=False,
    ).ratio()

    return (
        .38 * token_jaccard
        + .22 * containment
        + .18 * bigram_dice
        + .12 * chargram_dice
        + .10 * sequence_ratio
    )


def similarity(a, b):
    """Compare plot-bearing fields with token, phrase, and character overlap."""
    fields = (
        ('conflict', .34),
        ('evidence', .24),
        ('reversal', .24),
        ('ending', .08),
        ('title', .06),
        ('hero', .02),
        ('antagonist', .02),
    )
    weighted = sum(_text_similarity(a.get(key, ''), b.get(key, '')) * weight
                   for key, weight in fields)
    return round(weighted, 3)


def unique_candidates(item, candidates, limit=5):
    found = sorted(((similarity(item, other), other) for other in candidates if other.get('id') != item.get('id')),
                   key=lambda p: p[0], reverse=True)
    return [(s, o) for s, o in found[:limit] if s >= .26]


def default_db():
    return {'version': 2, 'library': seed_bank(), 'days': {}, 'history': [], 'retired_idea_ids': [],
            'prompt_templates': {'full': '', 'part1': '', 'part2': '', 'image': ''},
            'planning_prompt': ''}


def normalized_db(raw):
    if not isinstance(raw, dict):
        raise ValueError('Dữ liệu sao lưu không hợp lệ.')
    if raw.get('version') != 2:
        raise ValueError('Không đúng định dạng dữ liệu Story42 phiên bản 2.')
    if not isinstance(raw.get('days'), dict) or not isinstance(raw.get('library'), list):
        raise ValueError('File thiếu library hoặc days.')
    retired_ids = raw.setdefault('retired_idea_ids', [])
    if not isinstance(retired_ids, list) or any(not isinstance(idea_id, str) for idea_id in retired_ids):
        raise ValueError('Danh sách ý tưởng đã xóa không hợp lệ.')
    if any(not isinstance(v, dict) or not isinstance(v.get('items'), list) for v in raw['days'].values()):
        raise ValueError('Cấu trúc ngày làm việc không hợp lệ.')
    raw.setdefault('history', [])
    templates = raw.setdefault('prompt_templates', {})
    if not isinstance(templates, dict):
        raise ValueError('Cấu hình template prompt không hợp lệ.')
    for mode in ('full', 'part1', 'part2', 'image'):
        value = templates.setdefault(mode, '')
        if not isinstance(value, str):
            raise ValueError(f'Template {mode} phải là chuỗi.')
    planning_prompt = raw.setdefault('planning_prompt', '')
    if not isinstance(planning_prompt, str):
        raise ValueError('Prompt bổ sung ý tưởng phải là chuỗi.')
    for day in raw['days'].values():
        for item in day['items']:
            item.setdefault('notes', '')
            item.setdefault('favorite', False)
            item.setdefault('draft', False)
            if not isinstance(item['notes'], str) or not isinstance(item['favorite'], bool) or not isinstance(item['draft'], bool):
                raise ValueError('Metadata brief không hợp lệ.')
    return raw


def load_db(path=DATA_FILE):
    if not path.exists():
        return default_db()
    with path.open('r', encoding='utf-8') as f:
        return normalized_db(json.load(f))


def save_db(db, path=DATA_FILE):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    with temp.open('w', encoding='utf-8') as f:
        json.dump(db, f, ensure_ascii=False, indent=2)
    temp.replace(path)


def archived_ids(db):
    """All used brief IDs (starter AND imported): never recycle a past brief."""
    return {item['id'] for day in db['days'].values()
            for item in day.get('items', []) if item.get('id')}


def used_starter_ids(db):
    return {item['id'] for day in db['days'].values()
            for item in day.get('items', []) if item.get('source') == 'starter' and item.get('id')}


def all_archived(db, exclude_date=None):
    return [s for d, day in db['days'].items() if d != exclude_date for s in day['items']]


def assign_42(db, for_date):
    """Select 3 unpublished seeds per theme, 1 per AI; no exhausted seed is recycled."""
    used = archived_ids(db)
    by_theme = {}
    for s in db['library']:
        if s['id'] in used:
            continue
        by_theme.setdefault(s['theme'], []).append(s)
    missing = [(THEME_NAME[theme], 3 - len(by_theme.get(theme, [])))
               for theme, _ in THEMES if len(by_theme.get(theme, [])) < 3]
    if missing:
        return None, missing
    rng = random.Random(for_date)  # predictable ordering per date, no API
    chosen = []
    for theme, _ in THEMES:
        pool = by_theme[theme][:]
        rng.shuffle(pool)
        selected = pool[:3]
        for ai, s in enumerate(selected, 1):
            item = dict(s)
            item['uid'] = str(uuid.uuid4())
            item['ai'] = ai
            item['status'] = 'ready'
            item['theme'] = theme
            chosen.append(item)
    chosen.sort(key=lambda s: (s['ai'], [t for t, _ in THEMES].index(s['theme'])))
    for index, item in enumerate(chosen, 1):
        item['slot'] = index
    assert len(chosen) == TOTAL
    return chosen, []


def new_day(db, for_date):
    if for_date in db['days']:
        return False, 'Đã có danh sách cho ngày này.'
    items, missing = assign_42(db, for_date)
    if missing:
        return False, 'Kho ý tưởng mới không đủ: ' + '; '.join(f'{t}: thiếu {n}' for t, n in missing)
    db['days'][for_date] = {'items': items, 'created': dt.datetime.now().isoformat(timespec='seconds')}
    return True, 'Đã tạo 42 thẻ ý tưởng, mỗi AI nhận 14 thẻ.'


PROMPT_MODES = ('full', 'part1', 'part2', 'image')
PROMPT_VARIABLES = ('title', 'hero', 'antagonist', 'conflict', 'evidence', 'reversal', 'ending')
PROMPT_VARIABLE_PATTERN = re.compile(r'\{\{([a-zA-Z0-9_]+)\}\}')


def validate_prompt_template(content: str) -> str:
    if not isinstance(content, str):
        raise ValueError('Template prompt phải là chuỗi.')
    variables = sorted(set(PROMPT_VARIABLE_PATTERN.findall(content)))
    invalid = [name for name in variables if name not in PROMPT_VARIABLES]
    if invalid:
        raise ValueError('Biến không hợp lệ: ' + ', '.join(f'{{{{{name}}}}}' for name in invalid))
    return content


def render_prompt(item, mode: str, templates: dict[str, str]) -> str:
    if mode not in PROMPT_MODES:
        raise ValueError(f'Loại template không hợp lệ: {mode}.')
    template = validate_prompt_template(templates.get(mode, ''))
    if not template.strip():
        raise ValueError(f'Chưa cấu hình template {mode}. Hãy mở Cài đặt Prompt để nhập và lưu template.')
    values = {key: str(item.get(key, '')) for key in PROMPT_VARIABLES}
    return PROMPT_VARIABLE_PATTERN.sub(lambda match: values[match.group(1)], template)


def planning_prompt(db, date, ai):
    themes = '\n'.join(f'{index:02d}. {name}' for index, (_, name) in enumerate(THEMES, 1))
    existing = [s for s in db['days'].get(date, {}).get('items', []) if s.get('ai') != ai]
    historical = all_archived(db, exclude_date=date)
    recent = (existing + historical[-42:])[-70:]
    avoid = '\n'.join(f'- {s.get("title", "")}: {str(s.get("conflict", ""))[:80]} / {str(s.get("reversal", ""))[:80]}'
                      for s in recent)
    return f'''Create 14 COMPLETELY DIFFERENT ORIGINAL story BRIEFS for a Vietnamese operator producing
modern Philippine Taglish Facebook drama. Do NOT write full stories.
This is the 14-brief idea batch for AI {ai} on {date}.

One brief per category, in precisely this order:
{themes}

Aim for 14 different lead roles, antagonist actions, conflict types, evidence mechanisms,
and twist mechanisms. Every conflict must be concrete and every reversal provable without luck.
Do not recycle or lightly rename any concepts in the following exclusion list:
{avoid or '(none)'}

Output EXACTLY 14 lines, with no Markdown table, headings, explanations, numbering bullets or code fences.
Use exactly 8 fields on each line, separated by DOUBLE VERTICAL BARS ( || ).
Format:
NN || TITLE || PROTAGONIST || ANTAGONIST || UNFAIR ACTION || CONCRETE EVIDENCE || EVIDENCE-DRIVEN REVERSAL || SATISFYING ENDING
NN must be 01 through 14 in order; use English for all fields; DO NOT use || inside a field.
Only provide 14 succinct idea lines. No personal data, hacking, graphic or sexual material.'''


def parse_planner(text, ai):
    lines = []
    for raw in text.splitlines():
        line = raw.strip().strip('`').strip()
        if not line or ' || ' not in line:
            continue
        parts = [x.strip() for x in re.split(r'\s*\|\|\s*', line)]
        if len(parts) != 8:
            raise ValueError(f'Dòng {len(lines)+1} phải có 8 cột (NN + 7 nội dung), đang có {len(parts)}.')
        if not re.fullmatch(r'\d{1,2}', parts[0]):
            raise ValueError(f'Số thứ tự sai: {parts[0]!r}')
        if int(parts[0]) != len(lines) + 1:
            raise ValueError(f'Cần thứ tự {len(lines)+1:02}, nhận {parts[0]}.')
        if any(len(p) < 9 for p in parts[1:]):
            raise ValueError(f'Dòng {len(lines)+1}: có trường mô tả quá ngắn.')
        theme = THEMES[len(lines)][0]
        lines.append(dict(id=f'CUSTOM-{uuid.uuid4().hex[:12]}', source='imported', theme=theme,
                          title=parts[1], hero=parts[2], antagonist=parts[3],
                          conflict=parts[4], evidence=parts[5], reversal=parts[6], ending=parts[7], ai=ai))
    if len(lines) != 14:
        raise ValueError(f'Cần chính xác 14 dòng đúng định dạng. Hiện đọc được {len(lines)} dòng.')
    return lines


def count_status(items):
    return {k: sum(s.get('status') == k for s in items) for k in STATUS_LABEL}
