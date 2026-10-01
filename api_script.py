import requests
import pandas as pd

def get_users_data(users: list[str]) -> pd.DataFrame:
    results = []
    for user in users:
        try:
            res = requests.get(
                f"https://api.github.com/users/{user}",
                timeout=5,
            )
            res.raise_for_status()
            data = res.json()
            results.append({
                "user": data["login"],
                "name": data.get("name"),
                "public_repos": data["public_repos"],
                "followers": data["followers"],
            })
        except requests.exceptions.RequestException as e:
            print(f"[ERROR]  {user}: {e}")
    return pd.DataFrame(results)

if __name__ == "__main__":
    users = ["octocat", "torvalds", "gvanrossum"]
    df = get_users_data(users)
    print(df)
