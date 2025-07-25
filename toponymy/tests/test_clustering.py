from toponymy.clustering import (
    build_raw_cluster_layers,
    build_cluster_tree,
    centroids_from_labels,
    create_cluster_layers,
    _build_cluster_tree,
    ToponymyClusterer,
    KMeansClusterer,
    EVoCClusterer,
)
from toponymy.cluster_layer import ClusterLayerText
from sklearn.metrics import adjusted_mutual_info_score
import numpy as np

from sklearn.datasets import make_blobs
from sklearn.metrics import pairwise_distances
from scipy.optimize import linear_sum_assignment


def test_centroids_from_labels():
    for i in range(10):
        n_clusters = np.random.randint(5, 50)
        n_samples = np.random.randint(100, 1000)
        cluster_labels = np.random.randint(-1, n_clusters, n_samples)
        vector_data = np.random.random_sample((n_samples, 256))
        result = centroids_from_labels(cluster_labels, vector_data)
        expected = np.vstack(
            [
                (
                    vector_data[cluster_labels == i].mean(axis=0)
                    if np.sum(cluster_labels == i) > 0
                    else np.zeros(256)
                )
                for i in range(cluster_labels.max() + 1)
            ]
        )
        np.testing.assert_array_equal(result, expected)

def test_centroids_from_labels_no_jit():
    for i in range(10):
        n_clusters = np.random.randint(5, 50)
        n_samples = np.random.randint(100, 1000)
        cluster_labels = np.random.randint(-1, n_clusters, n_samples)
        vector_data = np.random.random_sample((n_samples, 256))
        result = centroids_from_labels.py_func(cluster_labels, vector_data)
        expected = np.vstack(
            [
                (
                    vector_data[cluster_labels == i].mean(axis=0)
                    if np.sum(cluster_labels == i) > 0
                    else np.zeros(256)
                )
                for i in range(cluster_labels.max() + 1)
            ]
        )
        np.testing.assert_array_equal(result, expected)

def test_build_cluster_tree():
    clusterable_data = np.vstack(
        [
            make_blobs(
                n_samples=1000,
                n_features=2,
                centers=5,
                center_box=(0.0, 1.0),
                cluster_std=0.05,
            )[0],
            np.random.random_sample((1000, 2)),
        ]
    )
    cluster_label_vectors = build_raw_cluster_layers(
        clusterable_data, min_clusters=5, min_samples=5
    )
    cluster_tree = build_cluster_tree(cluster_label_vectors)

    # Assert that every child cluster is contained in the parent cluster
    for parent, children in cluster_tree.items():
        for child in children:
            assert parent[0] > child[0]
            # Skip if parent is the artificial root node
            if parent[0] >= len(cluster_label_vectors):
                continue
            np.testing.assert_array_equal(
                (cluster_label_vectors[parent[0]] == parent[1])
                & (cluster_label_vectors[child[0]] == child[1]),
                cluster_label_vectors[child[0]] == child[1],
            )

    # Assert that every cluster is contained in the tree
    clusters_in_tree = sum(cluster_tree.values(), [])
    assert len(set(clusters_in_tree)) == len(clusters_in_tree)
    for i in range(len(cluster_label_vectors)):
        for j in range(cluster_label_vectors[i].max() + 1):
            if i == 0:
                assert (i, j) in clusters_in_tree
            else:
                assert (i, j) in clusters_in_tree and (i, j) in cluster_tree

def test_build_cluster_tree_no_jit():
    clusterable_data = np.vstack(
        [
            make_blobs(
                n_samples=1000,
                n_features=2,
                centers=5,
                center_box=(0.0, 1.0),
                cluster_std=0.05,
            )[0],
            np.random.random_sample((1000, 2)),
        ]
    )
    cluster_label_vectors = build_raw_cluster_layers(
        clusterable_data, min_clusters=5, min_samples=5
    )
    cluster_tree = {}
    raw_mapping = _build_cluster_tree.py_func(np.vstack(cluster_label_vectors))
    for parent_layer, parent_cluster, child_layer, child_cluster in raw_mapping:
        parent_name = (parent_layer, parent_cluster)
        if parent_name in cluster_tree:
            cluster_tree[parent_name].append((child_layer, child_cluster))
        else:
            cluster_tree[parent_name] = [(child_layer, child_cluster)]

    # Assert that every child cluster is contained in the parent cluster
    for parent, children in cluster_tree.items():
        for child in children:
            assert parent[0] > child[0]
            # Skip if parent is the artificial root node
            if parent[0] >= len(cluster_label_vectors):
                continue
            np.testing.assert_array_equal(
                (cluster_label_vectors[parent[0]] == parent[1])
                & (cluster_label_vectors[child[0]] == child[1]),
                cluster_label_vectors[child[0]] == child[1],
            )

    # Assert that every cluster is contained in the tree
    clusters_in_tree = sum(cluster_tree.values(), [])
    assert len(set(clusters_in_tree)) == len(clusters_in_tree)
    for i in range(len(cluster_label_vectors)):
        for j in range(cluster_label_vectors[i].max() + 1):
            if i == 0:
                assert (i, j) in clusters_in_tree
            else:
                assert (i, j) in clusters_in_tree and (i, j) in cluster_tree


def test_clusterer_class():
    clusterer = ToponymyClusterer(
        min_clusters=4,
        min_samples=5,
        base_min_cluster_size=10,
        next_cluster_size_quantile=0.8,
    )

    np.random.seed(0)
    clusterable_data = np.vstack(
        [
            make_blobs(
                n_samples=1000,
                n_features=2,
                centers=5,
                center_box=(0.0, 1.0),
                cluster_std=0.05,
                random_state=0,
            )[0],
            np.random.random_sample((100, 2)),
        ]
    )
    embedding_vectors = np.random.random_sample((1100, 256))
    cluster_label_vectors = build_raw_cluster_layers(
        clusterable_data, min_clusters=4, min_samples=5
    )
    cluster_layers, cluster_tree = create_cluster_layers(
        ClusterLayerText,
        clusterable_data,
        embedding_vectors,
        base_min_cluster_size=10,
        next_cluster_size_quantile=0.8,
        min_clusters=4,
        min_samples=5,
    )
    class_cluster_layers, class_tree = clusterer.fit_predict(
        clusterable_vectors=clusterable_data,
        embedding_vectors=embedding_vectors,
        layer_class=ClusterLayerText,
    )
    assert len(class_cluster_layers) == len(cluster_layers)
    assert all(
        adjusted_mutual_info_score(
            class_cluster_layers[i].cluster_labels, cluster_label_vectors[i]
        )
        == 1.0
        for i in range(len(cluster_layers))
    )
    cluster_distances = pairwise_distances(
        class_cluster_layers[0].centroid_vectors, cluster_layers[0].centroid_vectors
    )
    row_inds, col_inds = linear_sum_assignment(cluster_distances)
    mapping = dict(zip(row_inds, col_inds))
    for key in class_tree:
        subclusters = sorted(class_tree[key])
        found = False
        for other_subclusters in cluster_tree.values():
            if subclusters == sorted(
                [(x[0], mapping[x[1]]) for x in other_subclusters]
            ):
                found = True
                break
        if not found:
            print(subclusters)
            print(cluster_tree)
        assert found


def test_kmeans_clusterer_class():
    clusterer = KMeansClusterer(
        min_clusters=4,
        base_n_clusters=64,
    )

    clusterable_data, clusterable_labels = make_blobs(
        n_samples=1000,
        n_features=2,
        centers=5,
        center_box=(0.0, 1.0),
        cluster_std=0.05,
        random_state=0,
    )
    embedding_vectors = np.random.random_sample((1100, 256))

    class_cluster_layers, class_tree = clusterer.fit_predict(
        clusterable_vectors=clusterable_data,
        embedding_vectors=embedding_vectors,
        layer_class=ClusterLayerText,
    )
    assert len(class_cluster_layers) == 3
    assert all(
        adjusted_mutual_info_score(
            class_cluster_layers[i].cluster_labels, clusterable_labels
        )
        >= (0.25 * (i + 1))
        for i in range(len(class_cluster_layers))
    )

def test_evoc_clusterer_class():
    clusterer = EVoCClusterer(
        min_clusters=4,
        min_samples=5,
        base_min_cluster_size=10,
        next_cluster_size_quantile=0.8,
    )

    np.random.seed(0)
    clusterable_data, cluster_labels = make_blobs(
        n_samples=1000,
        n_features=128,
        centers=5,
        center_box=(0.0, 1.0),
        cluster_std=0.05,
        random_state=0,
    )
    class_cluster_layers, class_tree = clusterer.fit_predict(
        clusterable_vectors=clusterable_data,
        embedding_vectors=clusterable_data,
        layer_class=ClusterLayerText,
    )
    assert np.unique(class_cluster_layers[-1].cluster_labels).shape[0] >= 5 and np.unique(class_cluster_layers[-1].cluster_labels).shape[0] <= 7
    assert adjusted_mutual_info_score(
        class_cluster_layers[-1].cluster_labels[class_cluster_layers[-1].cluster_labels >= 0],
        cluster_labels[class_cluster_layers[-1].cluster_labels >= 0]
    ) >= 0.75


def test_max_layers_limit():
    """Test that max_layers parameter correctly limits the number of hierarchy levels."""
    # Create test data with many potential clusters
    np.random.seed(42)
    clusterable_data, _ = make_blobs(
        n_samples=2000,
        n_features=10,
        centers=50,
        center_box=(0.0, 1.0),
        cluster_std=0.05,
        random_state=42,
    )
    embedding_vectors = np.random.random_sample((2000, 256))
    
    # Test with max_layers=2
    clusterer_with_limit = ToponymyClusterer(
        min_clusters=4,
        min_samples=5,
        base_min_cluster_size=10,
        max_layers=2,  # Limit to 2 layers
    )
    
    layers_limited, _ = clusterer_with_limit.fit_predict(
        clusterable_vectors=clusterable_data,
        embedding_vectors=embedding_vectors,
        layer_class=ClusterLayerText,
    )
    
    assert len(layers_limited) == 2, f"Expected exactly 2 layers, got {len(layers_limited)}"
    
    # Test with max_layers=None (no limit)
    clusterer_no_limit = ToponymyClusterer(
        min_clusters=4,
        min_samples=5,
        base_min_cluster_size=10,
        max_layers=None,  # No limit
    )
    
    layers_unlimited, _ = clusterer_no_limit.fit_predict(
        clusterable_vectors=clusterable_data,
        embedding_vectors=embedding_vectors,
        layer_class=ClusterLayerText,
    )
    
    # Should create more than 2 layers when not limited
    assert len(layers_unlimited) >= 2, f"Expected at least 2 layers, got {len(layers_unlimited)}"
    
    # Test with different max_layers values
    for max_layers in [1, 3, 4]:
        clusterer = ToponymyClusterer(
            min_clusters=4,
            min_samples=5,
            base_min_cluster_size=10,
            max_layers=max_layers,
        )
        
        layers, _ = clusterer.fit_predict(
            clusterable_vectors=clusterable_data,
            embedding_vectors=embedding_vectors,
            layer_class=ClusterLayerText,
        )
        
        assert len(layers) <= max_layers, f"Expected at most {max_layers} layers, got {len(layers)}"