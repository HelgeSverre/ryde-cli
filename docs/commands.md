# Full command reference

Generated from the CLI parser. Regenerate with `uv run scripts/generate_command_reference.py`.

Run these commands as `uv run ryde …` in a checkout, or `uvx --from ryde-cli ryde …` anywhere.
Usage blocks below show argparse's executable name. Common options `--format`, `--output`, `--config`, `--base-url`, and `--mobile-type` also work after subcommands when passed as separate arguments.

## `ryde`

```text
usage: ryde [-h] [--version] [--config CONFIG] [--base-url BASE_URL]
            [--mobile-type MOBILE_TYPE]
            {login,account,rides,passes,payments,fees,summary,optimize,export,stats,skill} ...

Command-line interface for personal, read-only Ryde account data.

positional arguments:
  {login,account,rides,passes,payments,fees,summary,optimize,export,stats,skill}
    login               guided SMS login; requests at most one SMS per minute
    account             account data
    rides               ride history, detail, and opt-in route data
    passes              RidePass catalog, owned cards, and purchase/recharge
                        history
    payments            read-only payment order/recharge records
    fees                city fare/fee rule data
    summary             local summary of fetched ride history
    optimize            conservative current RidePass comparison against your
                        history
    export              fetch and save one supported read-only resource
    stats               fetch your data and open the bundled local map
                        dashboard
    skill               install the bundled Ryde workflow skill for Codex or
                        Claude

options:
  -h, --help            show this help message and exit
  --version             show program's version number and exit
  --config CONFIG       0600 token/config file (default: $RYDE_CONFIG or
                        ~/.config/ryde-cli/config.json)
  --base-url BASE_URL   override $RYDE_BASE_URL/config base URL
  --mobile-type MOBILE_TYPE
                        override $RYDE_MOBILE_TYPE/config Android descriptor
```

## `ryde login`

```text
usage: ryde login [-h] [--phone PHONE] [--country-code COUNTRY_CODE]
                  [--device DEVICE] [--phone-info PHONE_INFO]
                  [--latitude LATITUDE] [--longitude LONGITUDE] [--send-sms]
                  [--force] [--sms-code SMS_CODE]
                  [--format {json,csv,tsv,table}]

options:
  -h, --help            show this help message and exit
  --phone PHONE         local or E.164 phone number; omitted prompts
                        interactively
  --country-code COUNTRY_CODE
  --device DEVICE       stable Android-style device id; generated/saved when
                        omitted
  --phone-info PHONE_INFO
                        Android phone information string
  --latitude LATITUDE
  --longitude LONGITUDE
  --send-sms            explicitly send a code in non-interactive use
  --force               bypass the local 60 second duplicate-SMS guard
  --sms-code SMS_CODE   complete an already requested login without sending
                        another SMS
  --format {json,csv,tsv,table}
                        output format (JSON default)
```

## `ryde account`

```text
usage: ryde account [-h] [--format {json,csv,tsv,table}] [--output OUTPUT]
                    {profile,active-ride} ...

positional arguments:
  {profile,active-ride}
    profile             account/profile record
    active-ride         current ride status only; never changes ride state

options:
  -h, --help            show this help message and exit
  --format {json,csv,tsv,table}
                        output format (JSON default)
  --output OUTPUT       write results owner-only (0600) instead of stdout
```

## `ryde account profile`

```text
usage: ryde account profile [-h]

options:
  -h, --help  show this help message and exit
```

## `ryde account active-ride`

```text
usage: ryde account active-ride [-h]

options:
  -h, --help  show this help message and exit
```

## `ryde rides`

```text
usage: ryde rides [-h] [--format {json,csv,tsv,table}] [--output OUTPUT]
                  {list,detail,order,route} ...

positional arguments:
  {list,detail,order,route}
    list                all completed ride records in date range
    detail              one completed ride
    order               linked charge/order detail for a completed ride
    route               sensitive recorded route points

options:
  -h, --help            show this help message and exit
  --format {json,csv,tsv,table}
                        output format (JSON default)
  --output OUTPUT       write results owner-only (0600) instead of stdout
```

## `ryde rides list`

```text
usage: ryde rides list [-h] [--start START] [--end END]

options:
  -h, --help     show this help message and exit
  --start START
  --end END
```

## `ryde rides detail`

```text
usage: ryde rides detail [-h] use_id

positional arguments:
  use_id

options:
  -h, --help  show this help message and exit
```

## `ryde rides order`

```text
usage: ryde rides order [-h] order_id

positional arguments:
  order_id

options:
  -h, --help  show this help message and exit
```

## `ryde rides route`

```text
usage: ryde rides route [-h] [--include-location] use_id

positional arguments:
  use_id

options:
  -h, --help          show this help message and exit
  --include-location  required acknowledgement for sensitive GPS data
```

## `ryde passes`

```text
usage: ryde passes [-h] [--format {json,csv,tsv,table}] [--output OUTPUT]
                   {catalogue,owned,history} ...

positional arguments:
  {catalogue,owned,history}
    catalogue           current city RidePass catalogue/prices
    owned               currently owned/active cards
    history             recharge/pass purchase history

options:
  -h, --help            show this help message and exit
  --format {json,csv,tsv,table}
                        output format (JSON default)
  --output OUTPUT       write results owner-only (0600) instead of stdout
```

## `ryde passes catalogue`

```text
usage: ryde passes catalogue [-h] --city-id CITY_ID

options:
  -h, --help         show this help message and exit
  --city-id CITY_ID
```

## `ryde passes owned`

```text
usage: ryde passes owned [-h]

options:
  -h, --help  show this help message and exit
```

## `ryde passes history`

```text
usage: ryde passes history [-h] [--page PAGE] [--all]

options:
  -h, --help   show this help message and exit
  --page PAGE
  --all        page through all available history
```

## `ryde payments`

```text
usage: ryde payments [-h] [--format {json,csv,tsv,table}] [--output OUTPUT]
                     {vipps,recharge-detail,month-amount,recharge-month} ...

positional arguments:
  {vipps,recharge-detail,month-amount,recharge-month}
    vipps               Vipps order history
    recharge-detail     one recharge receipt/detail
    month-amount        one month of account amount data
    recharge-month      one month of recharge data

options:
  -h, --help            show this help message and exit
  --format {json,csv,tsv,table}
                        output format (JSON default)
  --output OUTPUT       write results owner-only (0600) instead of stdout
```

## `ryde payments vipps`

```text
usage: ryde payments vipps [-h] [--page PAGE] [--all]

options:
  -h, --help   show this help message and exit
  --page PAGE
  --all
```

## `ryde payments recharge-detail`

```text
usage: ryde payments recharge-detail [-h] recharge_id

positional arguments:
  recharge_id

options:
  -h, --help   show this help message and exit
```

## `ryde payments month-amount`

```text
usage: ryde payments month-amount [-h] month

positional arguments:
  month       YYYY-MM

options:
  -h, --help  show this help message and exit
```

## `ryde payments recharge-month`

```text
usage: ryde payments recharge-month [-h] month

positional arguments:
  month       YYYY-MM

options:
  -h, --help  show this help message and exit
```

## `ryde fees`

```text
usage: ryde fees [-h] [--format {json,csv,tsv,table}] [--output OUTPUT]
                 --city-id CITY_ID

options:
  -h, --help            show this help message and exit
  --format {json,csv,tsv,table}
                        output format (JSON default)
  --output OUTPUT       write results owner-only (0600) instead of stdout
  --city-id CITY_ID
```

## `ryde summary`

```text
usage: ryde summary [-h] [--format {json,csv,tsv,table}] [--output OUTPUT]
                    [--start START] [--end END]

options:
  -h, --help            show this help message and exit
  --format {json,csv,tsv,table}
                        output format (JSON default)
  --output OUTPUT       write results owner-only (0600) instead of stdout
  --start START
  --end END
```

## `ryde optimize`

```text
usage: ryde optimize [-h] [--format {json,csv,tsv,table}] [--output OUTPUT]
                     [--start START] [--end END] --city-id CITY_ID

options:
  -h, --help            show this help message and exit
  --format {json,csv,tsv,table}
                        output format (JSON default)
  --output OUTPUT       write results owner-only (0600) instead of stdout
  --start START
  --end END
  --city-id CITY_ID
```

## `ryde export`

```text
usage: ryde export [-h] [--format {json,csv,tsv,table}] [--output OUTPUT]
                   [--start START] [--end END] [--city-id CITY_ID]
                   [--page PAGE] [--all]
                   {rides,profile,catalogue,owned-passes,recharges,vipps,fee-rule,summary,recommendation}

positional arguments:
  {rides,profile,catalogue,owned-passes,recharges,vipps,fee-rule,summary,recommendation}

options:
  -h, --help            show this help message and exit
  --format {json,csv,tsv,table}
                        output format (JSON default)
  --output OUTPUT       write results owner-only (0600) instead of stdout
  --start START
  --end END
  --city-id CITY_ID     needed for catalogue/fee-rule/recommendation (default
                        15)
  --page PAGE
  --all
```

## `ryde stats`

```text
usage: ryde stats [-h] [--format {json,csv,tsv,table}] [--output OUTPUT]
                  [--start START] [--end END] [--include-location]
                  [--data-dir DATA_DIR] [--fetch-only | --no-fetch]
                  [--no-open] [--port PORT] [--ttl TTL] [--stop URL]

options:
  -h, --help            show this help message and exit
  --format {json,csv,tsv,table}
                        output format (JSON default)
  --output OUTPUT       write results owner-only (0600) instead of stdout
  --start START
  --end END
  --include-location    also fetch precise stored GPS traces (otherwise use
                        ride endpoints)
  --data-dir DATA_DIR   override the private, account-scoped dataset directory
  --fetch-only          fetch data without starting a server
  --no-fetch            open an already prepared dataset without API requests
  --no-open             return the URL without opening a browser
  --port PORT           loopback port; 0 selects a free port
  --ttl TTL             server lifetime in seconds (1–86400; default 3600)
  --stop URL            stop a dashboard using its exact returned URL
```

## `ryde skill`

```text
usage: ryde skill [-h] [--format {json,csv,tsv,table}] --agent {codex,claude}
                  [--scope {project,user}] [--force]

options:
  -h, --help            show this help message and exit
  --format {json,csv,tsv,table}
                        output format (JSON default)
  --agent {codex,claude}
  --scope {project,user}
                        installation scope (default: current project)
  --force               replace existing skill files
```
