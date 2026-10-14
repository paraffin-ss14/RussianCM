using System;
using System.Collections.Generic;
using System.Data;
using Microsoft.EntityFrameworkCore;

namespace Content.Server._RuCM.Database;

/// <summary>
/// Repairs local SQLite databases whose schema already contains columns that a pending migration
/// tries to add (e.g. the database was migrated earlier on another branch under a different migration id).
/// Without this, <c>Migrate()</c> fails with "duplicate column name" and the server can't start.
/// </summary>
public static class RuCMSqliteMigrationRepair
{
    private const string RepairPendingProfileModel = "20261004212448_RepairPendingProfileModel";
    private const string ProductVersion = "10.0.6";

    private static readonly string[] ProfileLoadoutColumns = { "custom_color", "custom_entity", "custom_name" };

    public static void Run(DbContext context)
    {
        var connection = context.Database.GetDbConnection();
        var wasOpen = connection.State == ConnectionState.Open;
        if (!wasOpen)
            connection.Open();

        try
        {
            if (!TableExists(connection, "__EFMigrationsHistory") ||
                !TableExists(connection, "profile_loadout") ||
                MigrationApplied(connection, RepairPendingProfileModel))
            {
                return;
            }

            var existing = GetColumns(connection, "profile_loadout");
            var anyExists = false;
            foreach (var column in ProfileLoadoutColumns)
            {
                if (existing.Contains(column))
                    anyExists = true;
            }

            // Fresh or normal database: let the migration add the columns itself.
            if (!anyExists)
                return;

            using var transaction = connection.BeginTransaction();

            foreach (var column in ProfileLoadoutColumns)
            {
                if (!existing.Contains(column))
                    Execute(connection, transaction, $"ALTER TABLE profile_loadout ADD COLUMN {column} TEXT NULL;");
            }

            using (var cmd = connection.CreateCommand())
            {
                cmd.Transaction = transaction;
                cmd.CommandText = "INSERT INTO __EFMigrationsHistory (MigrationId, ProductVersion) VALUES ($id, $version);";
                AddParameter(cmd, "$id", RepairPendingProfileModel);
                AddParameter(cmd, "$version", ProductVersion);
                cmd.ExecuteNonQuery();
            }

            transaction.Commit();
        }
        finally
        {
            if (!wasOpen)
                connection.Close();
        }
    }

    private static bool TableExists(IDbConnection connection, string table)
    {
        using var cmd = connection.CreateCommand();
        cmd.CommandText = "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name = $name;";
        AddParameter(cmd, "$name", table);
        return Convert.ToInt64(cmd.ExecuteScalar()) > 0;
    }

    private static bool MigrationApplied(IDbConnection connection, string migrationId)
    {
        using var cmd = connection.CreateCommand();
        cmd.CommandText = "SELECT COUNT(*) FROM __EFMigrationsHistory WHERE MigrationId = $id;";
        AddParameter(cmd, "$id", migrationId);
        return Convert.ToInt64(cmd.ExecuteScalar()) > 0;
    }

    private static HashSet<string> GetColumns(IDbConnection connection, string table)
    {
        var columns = new HashSet<string>();
        using var cmd = connection.CreateCommand();
        cmd.CommandText = $"PRAGMA table_info({table});";
        using var reader = cmd.ExecuteReader();
        while (reader.Read())
        {
            columns.Add(reader.GetString(1));
        }

        return columns;
    }

    private static void Execute(IDbConnection connection, IDbTransaction transaction, string sql)
    {
        using var cmd = connection.CreateCommand();
        cmd.Transaction = transaction;
        cmd.CommandText = sql;
        cmd.ExecuteNonQuery();
    }

    private static void AddParameter(IDbCommand cmd, string name, object value)
    {
        var parameter = cmd.CreateParameter();
        parameter.ParameterName = name;
        parameter.Value = value;
        cmd.Parameters.Add(parameter);
    }
}
