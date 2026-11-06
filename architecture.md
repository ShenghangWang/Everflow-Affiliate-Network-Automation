# Offer cycle architecture

The Offer brings the advertiser's terms, the channel's capacity, the delivery configuration and the buyer's evidence into one operating record. This local demonstration exercises a single cost-per-lead Offer and shows where owners decide what happens next.

```mermaid
flowchart LR
    A[Advertiser and terms] --> C[Channel placement and capacity]
    C --> V[Versioned Offer configuration]
    V --> T[Mock platform test]
    T --> R[Exact version release]
    R --> D[Qualification and simulated delivery]
    D --> B[Buyer outcomes]
    B --> F[Finance review]
    B --> Q[Quality and capacity evidence]
    Q --> BD[BD negotiation recommendation]
    Q --> AM[AM channel recommendation]
    Q --> O[AdOps routing recommendation]
```

| Handoff | Accountable role | Evidence used for the decision |
| --- | --- | --- |
| Advertiser intake to Offer | BD | Advertiser identity and versioned commercial terms, including currency, revenue per lead and cap |
| Offer to channel placement | AM | Channel and Sub-ID, placement approval and configured capacity for the current UTC day |
| Channel placement to test | AdOps | Configuration version and fingerprint, exact platform mapping and mock test record with adapter rule version |
| Passing test to release | Launch owner | Latest passing test of the current configuration, readiness checks and owner verification note |
| Lead receipt to buyer delivery | AdOps | Qualification facts, rejection reasons and mock delivery outcome bound to the release and channel |
| Delivery to outcomes | Buyer feedback owner | Outcome rows tied to the delivered batch, with a versioned feedback ID for corrections |
| Outcomes to Finance | Finance | Retained delivery and feedback references, provisional totals for the normal fixture or an owned hold for disputed returns |
| Outcomes and capacity to next actions | BD, AM and AdOps | Exact batch quality, current day capacity and named recommendations for commercial review, channel health and routing |

## State and authority

React presents the Offer workflow and sends typed actions to FastAPI. The service checks expected configuration versions and records changes in a SQLite transaction. Configuration, test, release, batch, feedback and reconciliation records retain their references. A material configuration change or a new test requires fresh release evidence. Delivery requires the current exact release and consumes the daily cap and channel capacity across batches.

A repeated event ID with the same request reuses the recorded operation. A changed request under that ID conflicts. A failed, unknown or superseded test cannot release a configuration. Buyer outcomes stay unknown until the relevant feedback arrives. A Finance preview requires the latest reviewed feedback ID for its batch. Later feedback supersedes the previous conclusion and retains its history.

Quality is measured on the exact synthetic batch. Capacity is the configured channel ceiling minus server-counted deliveries for the current UTC day. They have separate time windows. BD, AM and AdOps can see how those facts inform a recommendation. The current demo records those recommendations as local evidence and uses owner labels from the fixture.

## Integration boundaries

The application owns version checks, eligibility, release and provisional arithmetic. The Everflow adapter in this demo simulates mapping and postback verification for the cost-per-lead path. A live adapter would require confirmed account scope, tested request and readback contracts and real operator authority. Ringba number and target mapping, duration qualification and call outcomes would use a separate adapter. The demo keeps platform actions, qualification checks and buyer outcomes simulated.

The server binds to loopback and runs one worker against a local database. The fixture approximates base margin using revenue and base channel cost. Full cost, bonus, reserve and return accounting require approved definitions. Real pricing, routing, billing and payout actions require confirmed rules and authorized access.

## Open employer decisions

| Decision | Treatment in the demo |
| --- | --- |
| Does the 72-hour return window start at lead generation or delivery? | Keep event times and hold disputed returns for Finance until the start event and boundary are confirmed. This is distinct from the historical BD no-response timer. |
| Does Tier 1 require volume and quality or either condition? | Keep qualification and outcome evidence available for review. Tier repricing remains a commercial decision. |
| Can an above-cap upstream return create a supplier deduction? | Keep upstream billing and downstream deduction decisions separate. A disputed return holds both provisional totals and stays with Finance. |

## Historical architecture

The [Day 1 architecture at `033795f`](https://github.com/ShenghangWang/Everflow-Affiliate-Network-Automation/blob/033795f9be852c46ed34f87f3504d21dfa759bee/architecture.md) describes the earlier roles, source mapping, proposal review, recurring AM and reconciliation workflows. See the [Offer demo guide](docs/offer-demo.md) for the current entry points and verification commands.
