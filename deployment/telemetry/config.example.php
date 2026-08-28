<?php
declare(strict_types=1);

// Copy outside the public web root and set INNAWARE_TELEMETRY_CONFIG to its
// absolute path in the Apache/PHP-FPM environment.
return [
    'dsn' => 'mysql:host=127.0.0.1;port=3306;dbname=innaware_telemetry;charset=utf8mb4',
    'username' => 'innaware_telemetry_writer',
    'password' => 'replace-with-a-long-random-password',
];
