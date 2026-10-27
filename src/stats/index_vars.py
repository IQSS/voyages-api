import re

big_df={
  "endpoint": "voyage/dataframes/",
  "schema_name": "Voyage",
  "name": "big_df",
  "variables": {
    "id": {
      "type": "int"
    },
    "dataset": {
      "type": "int"
    },
    "voyage_id": {
      "type": "int",
      "label": "Voyage ID"
    },
	"voyage_ship__ship_name": {
		"type": "str",
		"label": "Name of vessel"
	},
    "voyage_dates__imp_arrival_at_port_of_dis_sparsedate__year": {
      "type": "int",
      "label": "Year arrived with captives"
    },
    "voyage_slaves_numbers__imp_total_num_slaves_disembarked": {
      "type": "int",
      "label": "Total disembarked (IMP)"
    },
    "voyage_slaves_numbers__imp_total_num_slaves_embarked": {
      "type": "int",
      "label": "Total embarked (IMP)"
    },
    "voyage_dates__length_middle_passage_days": {
      "type": "int",
      "label": "Duration of captives' crossing (in days)"
    },
    "voyage_dates__imp_length_home_to_disembark": {
      "type": "int",
      "label": "Voyage duration, homeport to disembarkation (in days)"
    },
    "voyage_crew__crew_first_landing": {
      "type": "int",
      "label": "Crew at first landing of captives"
    },
    "voyage_crew__crew_voyage_outset": {
      "type": "int",
      "label": "Crew at voyage outset"
    },
    "voyage_ship__tonnage_mod": {
      "type": "int",
      "label": "Standardized Tonnage (IMP)"
    },
    "voyage_slaves_numbers__imp_jamaican_cash_price": {
      "type": "int",
      "label": "Sterling cash price in Jamaica (IMP)"
    },
    "voyage_slaves_numbers__imp_mortality_ratio": {
      "type": "pct",
      "label": "Percentage of captives who died during crossing (IMP)"
    },
    "voyage_slaves_numbers__percentage_women_among_landed_slaves": {
      "type": "pct",
      "label": "Percentage of women among landed slaves"
    },
    "voyage_outcome__vessel_captured_outcome__name": {
      "type": "str",
      "label": "Outcome of voyage if ship captured"
    },
    "voyage_ship__imputed_nationality__name": {
      "type": "str",
      "label": "Flag of vessel (IMP)"
    },
    "voyage_itinerary__imp_region_voyage_begin__name": {
      "type": "obj",
      "label": "Imputed region where voyage began",
      "re_cleanup": {
        "type": "sub",
        "find": "\.",
        "replace": "",
        "flags": re.DOTALL
      },
      "fields":["voyage_itinerary__imp_region_voyage_begin__name"]
    },
    "voyage_ship__rig_of_vessel__name": {
      "type": "str",
      "label": "Rig of Vessel"
    },
    "voyage_itinerary__place_voyage_ended__name": {
      "type": "str",
      "label": "Place where vessel's voyage ended"
    },
    "voyage_dates__slave_purchase_began_sparsedate": {
      "type": "obj",
      "label": "Date purchase of captives began",
      "join": ",",
      "fields":[
      	"voyage_dates__slave_purchase_began_sparsedate__year",
      	"voyage_dates__slave_purchase_began_sparsedate__month",
      	"voyage_dates__slave_purchase_began_sparsedate__day"
      	]
    },
    "voyage_slaves_numbers__percentage_men": {
      "type": "pct",
      "label": "Percent men"
    },
    "voyage_dates__voyage_completed_sparsedate": {
      "type": "obj",
      "label": "Date voyage completed",
      "join": ",",
      "fields":[
      	"voyage_dates__voyage_completed_sparsedate__year",
      	"voyage_dates__voyage_completed_sparsedate__month",
      	"voyage_dates__voyage_completed_sparsedate__day"
      	]
    },
    "voyage_itinerary__region_of_return__name": {
      "type": "obj",
      "label": "Region of return",
      "re_cleanup": {
        "type": "sub",
        "find": "\.",
        "replace": "",
        "flags": re.DOTALL
      },
      "fields":["voyage_itinerary__region_of_return__name"]
    },
    "voyage_slaves_numbers__percentage_boy": {
      "type": "pct",
      "label": "Percent boys"
    },
    "voyage_itinerary__imp_principal_region_slave_dis__name": {
      "type": "obj",
      "label": "Imputed principal region of captive disembarkation",
      "re_cleanup": {
        "type": "sub",
        "find": "\.",
        "replace": "",
        "flags": re.DOTALL
      },
      "fields":["voyage_itinerary__imp_principal_region_slave_dis__name"]
    },
    "voyage_itinerary__imp_principal_region_of_slave_purchase__name": {
      "type": "obj",
      "label": "Imputed Principal region of captive purchase",
      "re_cleanup": {
        "type": "sub",
        "find": "\.",
        "replace": "",
        "flags": re.DOTALL
      },
      "fields":["voyage_itinerary__imp_principal_region_of_slave_purchase__name"]
    },
    "voyage_dates__date_departed_africa_sparsedate": {
      "type": "obj",
      "label": "Date vessel departed Africa",
      "join": ",",
      "fields":[
        "voyage_dates__date_departed_africa_sparsedate__year",
      	"voyage_dates__date_departed_africa_sparsedate__month",
      	"voyage_dates__date_departed_africa_sparsedate__day"
      	]
    },
    "voyage_dates__voyage_began_sparsedate": {
      "type": "obj",
      "label": "Date voyage began",
      "join": ",",
      "fields":[
        "voyage_dates__voyage_began_sparsedate__year",
      	"voyage_dates__voyage_began_sparsedate__month",
      	"voyage_dates__voyage_began_sparsedate__day"
      	]
    },
    "voyage_itinerary__imp_port_voyage_begin__name": {
      "type": "obj",
      "label": "Imputed Place where vessel's voyage began",
      "re_cleanup": {
        "type": "sub",
        "find": "\.",
        "replace": "",
        "flags": re.DOTALL
      },
      "fields":["voyage_itinerary__imp_port_voyage_begin__name"]
    },
    "voyage_dates__first_dis_of_slaves_sparsedate": {
      "type": "obj",
      "label": "Date first disembarkation of captives",
      "join": ",",
      "fields":[
        "voyage_dates__first_dis_of_slaves_sparsedate__year",
      	"voyage_dates__first_dis_of_slaves_sparsedate__month",
      	"voyage_dates__first_dis_of_slaves_sparsedate__day"
      	]
    },
    "voyage_itinerary__imp_broad_region_slave_dis__name": {
      "type": "str",
      "label": "Broad region of captive disembarkation (IMP)"
    },
    "voyage_slaves_numbers__percentage_girl": {
      "type": "pct",
      "label": "Percent girls"
    },
    "voyage_outcome__particular_outcome__name": {
      "type": "str",
      "label": "Particular outcome"
    },
    "voyage_itinerary__imp_principal_port_slave_dis__name": {
      "type": "obj",
      "label": "Imputed principal port of captive disembarkation",
      "re_cleanup": {
        "type": "sub",
        "find": "\.",
        "replace": "",
        "flags": re.DOTALL
      },
      "fields":["voyage_itinerary__imp_principal_port_slave_dis__name"]
    },
    "voyage_slaves_numbers__percentage_child": {
      "type": "pct",
      "label": "Percent children"
    },
    "voyage_slaves_numbers__percentage_women": {
      "type": "pct",
      "label": "Percentage women on voyage"
    },
    "voyage_dates__departure_last_place_of_landing_sparsedate": {
      "type": "obj",
      "label": "Date departed last place of landing",
      "join": ",",
      "fields":[
        "voyage_dates__departure_last_place_of_landing_sparsedate__year",
      	"voyage_dates__departure_last_place_of_landing_sparsedate__month",
      	"voyage_dates__departure_last_place_of_landing_sparsedate__day"
      	]
    },
    "voyage_outcome__outcome_owner__name": {
      "type": "str",
      "label": "Outcome of voyage for investors"
    },
    "voyage_outcome__outcome_slaves__name": {
      "type": "str",
      "label": "Outcome of voyage for captives"
    },
    "voyage_itinerary__imp_principal_place_of_slave_purchase__name": {
      "type": "obj",
      "label": "Imputed principal place of captive purchase",
      "re_cleanup": {
        "type": "sub",
        "find": "\.",
        "replace": "",
        "flags": re.DOTALL
      },
      "fields":["voyage_itinerary__imp_principal_place_of_slave_purchase__name"]
    },
    "voyage_outcome__resistance__name": {
      "type": "str",
      "label": "Resistance"
    },
    "voyage_slaves_numbers__percentage_male": {
      "type": "pct",
      "label": "Percent male"
    },
    "voyage_slaves_numbers__percentage_female": {
      "type": "pct",
      "label": "Percent female"
    },
    "voyage_itinerary__imp_broad_region_voyage_begin__name": {
      "type": "str",
      "label": "Broad region where voyage began (IMP)"
    },
    "voyage_itinerary__imp_broad_region_of_slave_purchase__name": {
      "type": "str",
      "label": "Broad region of captive purchase (IMP)"
    },
    "voyage_sources": {
      "type": "obj",
      "fields": [
        "voyage_source_connections__source__bib"
      ],
      "re_cleanup": {
        "type": "sub",
        "find": "<.*?>|\t|\n",
        "replace": "",
        "flags": re.DOTALL
      },
      "label": "Sources"
    },
    "enslavers": {
      "type": "obj",
      "fields": [
        "voyage_enslavement_relations__relation_enslavers__roles__name",
        "voyage_enslavement_relations__relation_enslavers__enslaver_alias__identity__principal_alias"
      ],
      "label":"Enslavers"
    }
  }
}


estimate_pivot_tables={
	'endpoint':'assessment/dataframes/',
	'schema_name':'Estimate',
	'name':'estimate_pivot_tables',
		'variables':{
	  "id": {
			"type": "int"
		},
		"nation__id": {
			"type": "int"
		},
		"nation__name": {
			"type": "str"
		},
		"nation__order_num": {
			"type": "int"
		},
		"embarkation_region__id": {
			"type": "int"
		},
		"embarkation_region__export_area__id": {
			"type": "int"
		},
		"embarkation_region__export_area__name": {
			"type": "str"
		},
		"embarkation_region__export_area__order_num": {
			"type": "int"
		},
		"embarkation_region__export_area__latitude": {
			"type": "int"
		},
		"embarkation_region__export_area__longitude": {
			"type": "int"
		},
		"embarkation_region__name": {
			"type": "str"
		},
		"embarkation_region__order_num": {
			"type": "int"
		},
		"embarkation_region__latitude": {
			"type": "int"
		},
		"embarkation_region__longitude": {
			"type": "int"
		},
		"disembarkation_region__id": {
			"type": "int"
		},
		"disembarkation_region__import_area__id": {
			"type": "int"
		},
		"disembarkation_region__import_area__name": {
			"type": "str"
		},
		"disembarkation_region__import_area__order_num": {
			"type": "int"
		},
		"disembarkation_region__import_area__latitude": {
			"type": "int"
		},
		"disembarkation_region__import_area__longitude": {
			"type": "int"
		},
		"disembarkation_region__name": {
			"type": "str"
		},
		"disembarkation_region__order_num": {
			"type": "int"
		},
		"disembarkation_region__latitude": {
			"type": "int"
		},
		"disembarkation_region__longitude": {
			"type": "int"
		},
		"year": {
			"type": "int"
		},
		"embarked_slaves": {
			"type": "int"
		},
		"disembarked_slaves": {
			"type": "int"
		}
	}

}

timelapse={
	'endpoint':'voyage/dataframes/',
	'schema_name':'Voyage',
	'name':'timelapse',
	'variables':{
		"id": {
			"type": "int"
		},
		"voyage_itinerary__imp_broad_region_of_slave_purchase__id": {
			"type": "int"
		},
		"voyage_itinerary__imp_principal_region_of_slave_purchase__id": {
			"type": "int"
		},
		"voyage_itinerary__imp_principal_place_of_slave_purchase__id": {
			"type": "int"
		},
		"voyage_itinerary__imp_broad_region_slave_dis__id": {
			"type": "int"
		},
		"voyage_itinerary__imp_principal_region_slave_dis__id": {
			"type": "int"
		},
		"voyage_itinerary__imp_principal_port_slave_dis__id": {
			"type": "int"
		},
		"voyage_slaves_numbers__imp_total_num_slaves_embarked": {
			"type": "int"
		},
		"voyage_slaves_numbers__imp_total_num_slaves_disembarked": {
			"type": "int"
		},
		"voyage_dates__imp_arrival_at_port_of_dis_sparsedate__year": {
			"type": "int"
		},
		"voyage_dates__imp_arrival_at_port_of_dis_sparsedate__month": {
			"type": "int"
		},
		"voyage_ship__imputed_nationality__value": {
			"type": "int"
		},
		"voyage_ship__tonnage_mod": {
			"type": "int"
		},
		"voyage_ship__ship_name": {
			"type": "str"
		}
	}
}

