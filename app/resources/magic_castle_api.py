from flask import request
from resources.api_view import ApiView
from exceptions.invalid_usage_exception import InvalidUsageException
from models.magic_castle import MagicCastle
from models.magic_castle_manager import MagicCastleManager
from models.cluster_status_code import ClusterStatusCode
from database.database_manager import DatabaseManager


class MagicCastleAPI(ApiView):
    def get(self, database_connection, hostname):

        if hostname:
            try:
                magic_castle = MagicCastle(database_connection, hostname)
                return magic_castle.dump_configuration()
            except InvalidUsageException as e:
                return e.get_response()
        else:
            return [
                {
                    "cluster_name": magic_castle.get_cluster_name(),
                    "domain": magic_castle.get_domain(),
                    "hostname": magic_castle.get_hostname(),
                    "status": magic_castle.get_status().value,
                }
                for magic_castle in MagicCastleManager(database_connection).all()
            ]

    def post(self, database_connection, hostname, apply=False):
        if apply:
            magic_castle = MagicCastle(database_connection, hostname)
            try:
                magic_castle.apply()
                return {}
            except InvalidUsageException as e:
                return e.get_response()
        else:
            magic_castle = MagicCastleManager(database_connection).create_empty_magic_castle()
            json_data = request.get_json()
            if not json_data:
                return {"message": "No json data was provided"}, 400

            try:
                magic_castle.load_configuration(json_data)
                magic_castle.plan_creation()
                return {}
            except InvalidUsageException as e:
                return e.get_response()

    def put(self, database_connection, hostname):
        magic_castle = MagicCastle(database_connection, hostname)
        json_data = request.get_json()

        if not json_data:
            return {"message": "No json data was provided"}, 400

        try:
            magic_castle.load_configuration(json_data)
            magic_castle.plan_modification()
            return {}
        except InvalidUsageException as e:
            return e.get_response()

    def delete(self, database_connection, hostname):
        magic_castle = MagicCastle(database_connection, hostname)
        try:
            magic_castle.plan_destruction()
            return {}
        except InvalidUsageException as e:
            return e.get_response()
