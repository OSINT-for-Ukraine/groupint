query_hint = """
You must pass with integer:

*N - fetch every nodes\n
intersection_more_than_N - retrieve the users with more than N intersection in the same groups\n
more_than_N_groups - retrieve the users with more than N groups

You must pass just:
the_most_groups_per_user - retrieve the users with the most groups\n
size_rating_for_groups - retrieve a rating of the groups ordered by the size\n
"""
