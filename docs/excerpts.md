# Excerpts

52 verbatim pinned-source excerpts in `fixtures/source-excerpts/`, re-derived by `scripts/extract_excerpts.py` from the pinned checkout. Line numbers were verified with `grep -n` on the local checkout of commit `0085a1ff885d6a446369cf73a4430f75af22be55`; no line number was taken from a web fetch. Blob SHAs and sizes come from `git hash-object` / file size on the checkout and are re-checked by `scripts/probe.py` (H-01).

| ID | File | Lines | Anchor |
| --- | --- | --- | --- |
| E01 | include/xrpl/basics/chrono.h | 45-72 | class NetClock |
| E02 | src/xrpld/core/TimeKeeper.h | 36-67 | std::chrono::system_clock::now() |
| E03 | src/xrpld/core/TimeKeeper.h | 69-86 | closeTime() const |
| E04 | src/xrpld/core/TimeKeeper.h | 88-116 | adjustCloseTime |
| E05 | src/xrpld/consensus/Validations.h | 40-56 | validationCURRENT_WALL |
| E06 | src/xrpld/consensus/Validations.h | 58-64 | validationCURRENT_LOCAL |
| E07 | src/xrpld/consensus/Validations.h | 66-71 | validationCURRENT_EARLY |
| E08 | src/xrpld/consensus/Validations.h | 73-79 | validationSET_EXPIRES |
| E09 | src/xrpld/consensus/Validations.h | 81-89 | validationFRESHNESS |
| E10 | src/xrpld/consensus/Validations.h | 137-166 | isCurrent( |
| E11 | src/xrpld/consensus/Validations.h | 615-627 | ValStatus::stale |
| E12 | src/xrpld/overlay/detail/PeerImp.cpp | 2446-2487 | setSeen(closeTime) |
| E13 | src/xrpld/consensus/Validations.h | 509-533 | isCurrent( |
| E14 | src/xrpld/consensus/Validations.h | 729-775 | expire(beast::Journal& j) |
| E15 | src/xrpld/consensus/Validations.h | 98-128 | SeqEnforcer |
| E16 | src/xrpld/consensus/Validations.h | 1127-1147 | laggards( |
| E17 | src/xrpld/app/consensus/RCLValidations.cpp | 117-126 | RCLValidationsAdaptor::now() |
| E18 | src/xrpld/app/consensus/RCLConsensus.cpp | 813-824 | validationTime |
| E19 | include/xrpl/protocol/STValidation.h | 231-253 | seenTime_(signTime) |
| E20 | src/libxrpl/protocol/STValidation.cpp | 111-119 | getSignTime |
| E21 | src/xrpld/consensus/LedgerTiming.h | 35-47 | ledgerPossibleTimeResolutions |
| E22 | src/xrpld/consensus/LedgerTiming.h | 78-122 | getNextLedgerTimeResolution |
| E23 | src/xrpld/consensus/LedgerTiming.h | 124-143 | roundCloseTime |
| E24 | src/xrpld/consensus/LedgerTiming.h | 154-169 | effCloseTime |
| E25 | src/xrpld/consensus/Consensus.h | 1507-1641 | closeTimeVotes |
| E26 | src/xrpld/app/consensus/RCLConsensus.cpp | 491-506 | prevLedger.closeTime() + 1s |
| E27 | src/xrpld/app/consensus/RCLConsensus.cpp | 704-728 | medianCloseOffset(rawCloseTimes) |
| E28 | src/xrpld/consensus/Consensus.cpp | 26-103 | ledgerMIN_CLOSE |
| E29 | src/xrpld/consensus/Consensus.cpp | 176-270 | checkConsensus( |
| E30 | src/xrpld/consensus/ConsensusParms.h | 134-157 | avalancheCutoffs |
| E31 | src/xrpld/consensus/Consensus.h | 1501-1529 | isStale(peerCutoff) |
| E32 | src/xrpld/app/misc/NetworkOPs.cpp | 1095-1103 | timerEntry(app_.timeKeeper().closeTime() |
| E33 | src/xrpld/consensus/Consensus.h | 1433-1447 | rawCloseTimes_.self = now_; |
| E34 | src/xrpld/app/ledger/detail/LedgerMaster.cpp | 364-398 | 5min |
| E35 | src/xrpld/consensus/ConsensusParms.h | 45-66 | validationVALID_WALL |
| E36 | src/xrpld/app/consensus/RCLConsensus.cpp | 1030-1042 | validators().expires() |
| E37 | src/xrpld/consensus/Consensus.h | 1179-1215 | previousCloseCorrect |
| E38 | docs/consensus.md | 145-169 | Effective Close Time |
| E39 | src/xrpld/consensus/ConsensusParms.h | 78-114 | ledgerMAX_CONSENSUS |
| E40 | src/xrpld/consensus/DisputedTx.h | 85-149 | avSTALLED_ROUNDS |
| E41 | src/xrpld/consensus/ConsensusParms.h | 68-72 | proposeFRESHNESS |
| E42 | src/xrpld/consensus/Consensus.h | 337-348 | clock_type |
| E43 | src/xrpld/consensus/ConsensusParms.h | 101-102 | ledgerGRANULARITY |
| E44 | src/xrpld/app/ledger/LedgerMaster.h | 116-121 | canBeCurrent |
| E45 | src/xrpld/app/ledger/Ledger.cpp | 377-389 | closeFlags |
| E46 | src/xrpld/consensus/ConsensusTypes.h | 191-260 | medianCloseOffset |
| E47 | src/xrpld/consensus/ConsensusProposal.h | 159-164 | isStale |
| E48 | include/xrpl/protocol/LedgerHeader.h | 82-87 | sLCF_NoConsensusTime |
| E49 | src/xrpld/consensus/Validations.h | 483-491 | withTrie |
| E50 | src/xrpld/consensus/ConsensusParms.h | 159-160 | avCT_CONSENSUS_PCT |
| E51 | src/xrpld/consensus/LedgerTiming.h | 49-53 | increaseLedgerTimeResolutionEvery |
| E52 | src/xrpld/consensus/ConsensusParms.h | 81-83 | ledgerIDLE_INTERVAL |

Digests and git blob SHAs: `fixtures/source-hashes.json` (21 source files).
