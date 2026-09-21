
Forbidden transactions:
  - "PENDING" to any other state issued by RECCURRENCY RULE -- a new intermediate state ("SKIPPED") must be submitted
  - "IN PROGRESS" to any other state issued by RECCURRENCY RULE -- a new intermediate state ("SKIPPED") must be submitted
  - "DELETED" to any other state



           <Begin>
              |
|------------>|<------------------------------------------|
|             V                                           |
|   |<----[PENDING]--------------->|----------->|  (RECCURRENCY RULE)
|   |                              |            |         ^
|   |                              |            |         |
|   |                              V            V         |
|   |                   |<--[IN PROGRESS]-->[SKIPPED*]--->|
|   |                   |          ^                      |
|   |                   |          |                      |
|   |                   |          |                      |
|   |                   |          |                      |
|   |---------->|<------|          |                      |
|               |                  |                      |
|               V                  |                      |
|<--------------|----------------->|                      |
|    ^          |             ^                           |
|    |          |             |                           |
|    |--------->|             |-------------------------->|
|    |          |             |
|    |          V             |
|    |    |<----|--->|        |
|    |    |          |        |
|    |    V          V        |
|    |  [DONE]   [CANCELLED]  |
|    |    |          |        |
|    |    |---->|<---|        |
|    |          |             |
|    |          V             |
|    |<---------|------------>|
|               |
|-->[DELETED]   |
        |       |
        |       |
        |-->|<--|
            |
            |
            V
          <End>
