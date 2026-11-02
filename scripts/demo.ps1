$wallet = "http://localhost:8001/api/v1/wallets"
$toll   = "http://localhost:8002/api/v1/crossings"
$json   = "application/json"

Write-Host "1. Create wallet"
Invoke-RestMethod -Method Post -Uri $wallet -ContentType $json -Body '{"fleet_id":"fleet-demo"}'

Write-Host "2. Top up 100000 paise"
Invoke-RestMethod -Method Post -Uri "$wallet/1/topup" -ContentType $json -Body '{"amount":100000,"reference_id":"demo-top-1"}'

# TODO: register vehicle TRUCK-1 for wallet 1 in the Vehicle Registry

$key = "demo-" + [guid]::NewGuid()
$body = '{"vehicle_id":"TRUCK-1","gate_id":"G1","amount":5000}'

Write-Host "3. Crossing (first call)"
Invoke-RestMethod -Method Post -Uri $toll -ContentType $json -Headers @{"Idempotency-Key"=$key} -Body $body

Write-Host "4. Same crossing again with the same key (should not charge twice)"
Invoke-RestMethod -Method Post -Uri $toll -ContentType $json -Headers @{"Idempotency-Key"=$key} -Body $body

Write-Host "5. Balance (expect 95000)"
Invoke-RestMethod -Uri "$wallet/1"