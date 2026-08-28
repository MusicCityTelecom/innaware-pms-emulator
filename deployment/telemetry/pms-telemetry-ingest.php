<?php
declare(strict_types=1);

header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');
header('X-Content-Type-Options: nosniff');

function respond(int $status, array $payload): never
{
    http_response_code($status);
    echo json_encode($payload, JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR);
    exit;
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    header('Allow: POST');
    respond(405, ['ok' => false, 'error' => 'method_not_allowed']);
}

$contentType = strtolower(trim(explode(';', $_SERVER['CONTENT_TYPE'] ?? '')[0]));
if ($contentType !== 'application/json') {
    respond(415, ['ok' => false, 'error' => 'application_json_required']);
}

$declaredLength = (int) ($_SERVER['CONTENT_LENGTH'] ?? 0);
if ($declaredLength > 4096) {
    respond(413, ['ok' => false, 'error' => 'request_too_large']);
}

$raw = file_get_contents('php://input', false, null, 0, 4097);
if ($raw === false || $raw === '' || strlen($raw) > 4096) {
    respond(400, ['ok' => false, 'error' => 'invalid_body']);
}

try {
    $payload = json_decode($raw, true, 8, JSON_THROW_ON_ERROR);
} catch (JsonException) {
    respond(400, ['ok' => false, 'error' => 'invalid_json']);
}

$allowed = ['event', 'version', 'platform', 'architecture', 'protocol_pack_version', 'install_id'];
if (!is_array($payload) || array_keys($payload) !== $allowed && array_diff(array_keys($payload), $allowed) !== []) {
    respond(400, ['ok' => false, 'error' => 'invalid_fields']);
}
foreach ($allowed as $field) {
    if (!array_key_exists($field, $payload) || !is_string($payload[$field])) {
        respond(400, ['ok' => false, 'error' => 'invalid_fields']);
    }
}

$event = $payload['event'];
$version = trim($payload['version']);
$platform = trim($payload['platform']);
$architecture = trim($payload['architecture']);
$packVersion = trim($payload['protocol_pack_version']);
$installId = strtolower(trim($payload['install_id']));

if (!in_array($event, ['install', 'run'], true)
    || !preg_match('/^\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?$/D', $version)
    || !preg_match('/^[a-z0-9_-]{1,24}$/D', $platform)
    || !preg_match('/^[a-z0-9_-]{1,24}$/D', $architecture)
    || !preg_match('/^[A-Za-z0-9._-]{1,64}$/D', $packVersion)
    || !preg_match('/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/D', $installId)
) {
    respond(422, ['ok' => false, 'error' => 'invalid_values']);
}

$configPath = getenv('INNAWARE_TELEMETRY_CONFIG');
if (!$configPath || !is_file($configPath)) {
    error_log('InnAware telemetry configuration is unavailable');
    respond(503, ['ok' => false, 'error' => 'service_unavailable']);
}
$config = require $configPath;

try {
    $pdo = new PDO($config['dsn'], $config['username'], $config['password'], [
        PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
        PDO::ATTR_EMULATE_PREPARES => false,
    ]);
    $pdo->beginTransaction();

    $limit = $pdo->prepare(
        "SELECT COUNT(*) FROM telemetry_events
         WHERE install_id = :install_id AND occurred_at >= UTC_TIMESTAMP(6) - INTERVAL 1 MINUTE"
    );
    $limit->execute(['install_id' => $installId]);
    if ((int) $limit->fetchColumn() >= 10) {
        $pdo->rollBack();
        respond(429, ['ok' => false, 'error' => 'rate_limited']);
    }

    $installation = $pdo->prepare(
        "INSERT INTO telemetry_installations
            (install_id, first_seen_at, last_seen_at, install_received, app_version, platform, architecture, protocol_pack_version)
         VALUES (:install_id, UTC_TIMESTAMP(6), UTC_TIMESTAMP(6), :install_received, :app_version, :platform, :architecture, :pack_version)
         ON DUPLICATE KEY UPDATE
            last_seen_at = UTC_TIMESTAMP(6),
            install_received = GREATEST(install_received, VALUES(install_received)),
            app_version = VALUES(app_version), platform = VALUES(platform),
            architecture = VALUES(architecture), protocol_pack_version = VALUES(protocol_pack_version)"
    );
    $installation->execute([
        'install_id' => $installId,
        'install_received' => $event === 'install' ? 1 : 0,
        'app_version' => $version,
        'platform' => $platform,
        'architecture' => $architecture,
        'pack_version' => $packVersion,
    ]);

    $insert = $pdo->prepare(
        "INSERT IGNORE INTO telemetry_events
            (install_id, event_type, event_key, occurred_at, app_version, platform, architecture, protocol_pack_version)
         VALUES (:install_id, :event_type, :event_key, UTC_TIMESTAMP(6), :app_version, :platform, :architecture, :pack_version)"
    );
    $insert->execute([
        'install_id' => $installId,
        'event_type' => $event,
        'event_key' => $event === 'install' ? $installId : null,
        'app_version' => $version,
        'platform' => $platform,
        'architecture' => $architecture,
        'pack_version' => $packVersion,
    ]);

    $pdo->commit();
    respond(200, ['ok' => true]);
} catch (Throwable $error) {
    if (isset($pdo) && $pdo->inTransaction()) {
        $pdo->rollBack();
    }
    error_log('InnAware telemetry ingestion failed: ' . $error->getMessage());
    respond(503, ['ok' => false, 'error' => 'service_unavailable']);
}
